"""
physics/body.py

Defines RigidBody: the physics representation of an object.
Now uses Mesh-based geometry for proper mass properties, inertia tensors,
and collision detection. Primitives are converted to meshes on creation.
"""

from __future__ import annotations

import copy
import itertools
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from geometry import Mesh
from math_utils import IDENTITY_QUAT, quat_integrate, vec3, quat_to_rotation_matrix, fast_cross3
from mesh import build_mesh_from_parts, get_mesh_by_kind, get_parts_recipe

logger = logging.getLogger(__name__)

SHAPE_SPHERE = "sphere"
SHAPE_BOX = "box"
SHAPE_CYLINDER = "cylinder"
SHAPE_CONE = "cone"
SHAPE_COMPOUND = "compound"

_id_counter = itertools.count(1)


# eq=False: every call site treats bodies by identity (`is`, `in` a list of
# distinct bodies). The default dataclass __eq__ compares numpy-array fields
# (position, velocity, ...) elementwise, which raises "the truth value of an
# array... is ambiguous" the moment two *different* bodies are compared -
# exactly what `body in world.bodies` does for every non-matching element.
@dataclass(eq=False)
class RigidBody:
    shape: str
    shape_params: dict
    position: np.ndarray = field(default_factory=lambda: vec3())
    velocity: np.ndarray = field(default_factory=lambda: vec3())
    orientation: np.ndarray = field(default_factory=lambda: IDENTITY_QUAT.copy())
    angular_velocity: np.ndarray = field(default_factory=lambda: vec3())
    mass: float = 1.0
    density: float = 1.0  # mass per unit volume
    scale: np.ndarray = field(default_factory=lambda: vec3(1.0, 1.0, 1.0))  # per-axis (sx, sy, sz)
    # Per-part scale overrides for composite (parts-recipe) objects, keyed
    # by the part's index in object_catalog.get_parts(object_kind). Lets
    # an individual placed instance resize one specific part (e.g. just
    # this car's wheels) without affecting the shared catalog template or
    # any other instance of the same kind - see set_part_scale().
    part_scale_overrides: dict = field(default_factory=dict)
    restitution: float = 0.5
    friction: float = 0.5
    is_static: bool = False
    is_asleep: bool = False
    sleep_timer: float = 0.0
    color: Tuple[float, float, float] = (0.7, 0.7, 0.7)
    object_kind: str = "shape"
    id: int = field(default_factory=lambda: next(_id_counter))

    # Mesh-based geometry (lazy-initialized)
    _mesh: Optional[Mesh] = None
    _local_inertia_tensor: Optional[np.ndarray] = None
    _inv_local_inertia_tensor: Optional[np.ndarray] = None
    _cached_R: Optional[np.ndarray] = None
    _cached_R_orientation: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        # Accept a plain float (old save files / callers passing a single
        # uniform scale factor) as well as a 3-vector, normalizing either
        # into a proper (sx, sy, sz) array - every method below assumes
        # self.scale is always a 3-element array.
        if isinstance(self.scale, (int, float)):
            s = float(self.scale)
            self.scale = vec3(s, s, s)
        else:
            self.scale = np.asarray(self.scale, dtype=np.float64)
        self._update_inv_mass()
        self._update_mass_from_density()
        self._update_inertia_tensors()

    # ------------------------------------------------------------------
    # Mass / density / scale
    # ------------------------------------------------------------------

    def _volume(self) -> float:
        """Unscaled base volume, derived from the actual mesh geometry -
        generically, for ANY object kind (primitive or compound/custom),
        rather than a per-shape analytic branch. This is what makes mass
        correct for the car/mug/rocket etc: previously their physics
        `shape` was a crude proxy (car="box", cup="cylinder") completely
        disconnected from their visible geometry; now it's whatever
        `self.mesh` actually is."""
        return abs(self.mesh.compute_volume())

    def _update_mass_from_density(self) -> None:
        """Compute mass = density * volume * (sx*sy*sz) - the product of
        the three axis scale factors is the volume-scaling factor for
        anisotropic scaling, generalizing the old scale**3 (which was only
        ever the sx=sy=sz special case)."""
        if self.is_static:
            self.mass = 0.0
            self.inv_mass = 0.0
            return
        vol = self._volume() * float(np.prod(self.scale))
        self.mass = max(0.001, self.density * vol)
        self._update_inv_mass()

    def _update_inv_mass(self) -> None:
        if self.is_static or self.mass <= 1e-9:
            self.inv_mass = 0.0
        else:
            self.inv_mass = 1.0 / self.mass

    def set_scale(self, new_scale) -> None:
        """Change scale and update mass/inertia accordingly. Accepts
        either a single number (uniform resize on all 3 axes - the common
        case, and what the property panel's main scale field uses) or a
        (sx, sy, sz) sequence for independent per-axis resizing."""
        if isinstance(new_scale, (int, float)):
            s = max(0.01, float(new_scale))
            self.scale = vec3(s, s, s)
        else:
            sx, sy, sz = new_scale
            self.scale = vec3(max(0.01, sx), max(0.01, sy), max(0.01, sz))
        self._update_mass_from_density()
        self._update_inertia_tensors()

    def set_part_scale(self, part_index: int, part_scale) -> None:
        """Resize ONE part of a composite (parts-recipe) object, for this
        specific instance only - the shared catalog template and every
        other placed instance of the same kind are unaffected. Accepts a
        single number (uniform on that part) or an (sx, sy, sz) sequence.

        Only meaningful for object kinds with a "parts" recipe (car, cup,
        rocket, ...) - for a bare primitive (a cube, a ball) there is only
        one implicit "part", which is exactly what the whole-object
        set_scale() already resizes, so this is a no-op for those kinds.
        """
        if isinstance(part_scale, (int, float)):
            s = max(0.01, float(part_scale))
            part_scale = (s, s, s)
        else:
            sx, sy, sz = part_scale
            part_scale = (max(0.01, sx), max(0.01, sy), max(0.01, sz))

        if part_scale == (1.0, 1.0, 1.0):
            self.part_scale_overrides.pop(part_index, None)
        else:
            self.part_scale_overrides[part_index] = part_scale

        self._mesh = None  # force a rebuild reflecting the new override
        self._update_mass_from_density()
        self._update_inertia_tensors()

    def set_mass(self, new_mass: float) -> None:
        """Change mass directly, keeping density consistent with the
        current volume (rather than leaving density stale after a direct
        mass edit), and updating the inertia tensor to match."""
        new_mass = max(0.001, new_mass)
        vol = self._volume() * float(np.prod(self.scale))
        if vol > 1e-9:
            self.density = new_mass / vol
        self.mass = new_mass
        self._update_inv_mass()
        self._update_inertia_tensors()

    def set_density(self, new_density: float) -> None:
        """Change density and update mass (and the inertia tensor, which
        depends on mass - previously left stale after a density edit)."""
        new_density = max(0.001, new_density)
        self.density = new_density
        self._update_mass_from_density()
        self._update_inertia_tensors()

    # ------------------------------------------------------------------
    # Mesh-based geometry
    # ------------------------------------------------------------------

    @property
    def mesh(self) -> Mesh:
        """Get the mesh for this body, creating it if necessary."""
        if self._mesh is None:
            self._mesh = self._create_mesh()
        return self._mesh

    def _create_mesh(self) -> Mesh:
        """Create the mesh for this body.

        Generic geometry pipeline (item 1/16 of the redesign): look the
        object kind up in the mesh registry FIRST - this is the single
        extension point for new geometry (a future user-created shape just
        needs a builder registered under its kind, via
        mesh.register_mesh_builder - nothing in this class needs to change
        for that). Only when no registered mesh exists for this kind
        (a bare primitive spawned directly by shape, e.g. from the physics
        debug tools) do we fall back to building straight from
        shape/shape_params.

        If this specific instance has part_scale_overrides (see
        set_part_scale), the shared cached mesh for this kind can't be
        used as-is - this instance needs its own mesh built from a
        modified copy of the kind's parts recipe with those specific
        parts' scale multiplied by the override, so resizing one part on
        one placed car doesn't affect the shared "car" template or any
        other car in the scene.
        """
        if self.part_scale_overrides:
            parts = get_parts_recipe(self.object_kind)
            if parts:
                parts = copy.deepcopy(parts)
                for idx, override in self.part_scale_overrides.items():
                    if 0 <= idx < len(parts):
                        base = parts[idx].get("scale", 1.0)
                        if isinstance(base, (int, float)):
                            base = (base, base, base)
                        parts[idx]["scale"] = tuple(b * o for b, o in zip(base, override))
                return build_mesh_from_parts(parts)

        registered = get_mesh_by_kind(self.object_kind)
        if registered is not None:
            return registered

        # Nothing registered for this kind - fall back to the bare
        # primitive named by self.shape, resolved through the SAME
        # registry (the primitives are registered kinds too), so there is
        # still no per-shape branching here. An unknown shape name yields
        # an empty Mesh rather than a guessed substitute, which surfaces
        # the problem instead of silently rendering the wrong thing.
        primitive = get_mesh_by_kind(self.shape)
        if primitive is not None:
            return primitive
        logger.warning(
            f"No geometry registered for kind={self.object_kind!r} / shape={self.shape!r}; "
            f"body {self.id} will have empty geometry"
        )
        return Mesh()

    def _update_inertia_tensors(self) -> None:
        """Update local and inverse local inertia tensors based on mesh geometry."""
        if self.is_static or self.mass <= 1e-9:
            self._local_inertia_tensor = np.eye(3, dtype=np.float64)
            self._inv_local_inertia_tensor = np.eye(3, dtype=np.float64)
            return

        # Get inertia tensor from mesh at current (possibly anisotropic) scale
        scaled_mesh = self.mesh.scale_nonuniform(self.scale)
        self._local_inertia_tensor = scaled_mesh.compute_inertia_tensor(self.mass)

        # Compute inverse
        try:
            self._inv_local_inertia_tensor = np.linalg.inv(self._local_inertia_tensor)
        except np.linalg.LinAlgError:
            # Fallback to diagonal approximation
            diag = np.diag(self._local_inertia_tensor)
            diag[diag < 1e-10] = 1e-10
            self._inv_local_inertia_tensor = np.diag(1.0 / diag)

    def get_rotation_matrix(self) -> np.ndarray:
        """3x3 world-space rotation matrix for the body's current
        orientation, cached and only recomputed when the orientation has
        actually changed. quat_to_rotation_matrix showed up as a real,
        measurable cost in a profiled physics step with many bodies -
        every contact test for a body was recomputing the same matrix from
        scratch, sometimes several times within a single substep (once per
        pair the body is involved in)."""
        if self._cached_R is None or not np.array_equal(self._cached_R_orientation, self.orientation):
            self._cached_R = quat_to_rotation_matrix(self.orientation)
            self._cached_R_orientation = self.orientation.copy()
        return self._cached_R

    def get_world_inertia_tensor(self) -> np.ndarray:
        """Get inertia tensor in world coordinates."""
        R = self.get_rotation_matrix()
        return R @ self._local_inertia_tensor @ R.T

    def get_world_inv_inertia_tensor(self) -> np.ndarray:
        """Get inverse inertia tensor in world coordinates."""
        R = self.get_rotation_matrix()
        return R @ self._inv_local_inertia_tensor @ R.T

    # ------------------------------------------------------------------
    # Bounding helpers (use scaled dimensions)
    # ------------------------------------------------------------------

    def bounding_radius(self) -> float:
        """Radius of the smallest sphere (centered at the local origin)
        guaranteed to contain the whole mesh, derived from actual mesh
        vertex positions - generic for any shape, not a per-shape analytic
        formula, and EXACT (not just an upper bound) for any mesh whose
        vertices all lie on its true bounding sphere - e.g. every vertex
        of create_sphere_mesh lies exactly on the sphere by construction,
        so this returns the exact radius, matching what sphere-sphere
        collision needs (an AABB-corner-distance upper bound would instead
        overestimate a sphere's radius by a factor of up to sqrt(3))."""
        if len(self.mesh.vertices) == 0:
            lo, hi = self.mesh.bounds
            corners = np.abs(np.stack([lo, hi])) * self.scale
            return float(np.max(np.linalg.norm(corners, axis=1)))
        scaled_verts = self.mesh.vertices * self.scale
        return float(np.max(np.linalg.norm(scaled_verts, axis=1)))

    def transformed_vertices(self) -> np.ndarray:
        """The mesh's vertices actually transformed by this body's current
        scale, orientation, and position - i.e. the real, current-frame
        world-space geometry. This is what ground placement and AABB
        computation must use to work for arbitrary rotation, arbitrary
        scale, and arbitrary (including asymmetric/hollow/custom) geometry,
        instead of an unscaled/unrotated shortcut like
        `position.y - primitive_height / 2`, which is only even correct for
        a symmetric primitive at identity orientation."""
        verts = self.mesh.vertices * self.scale
        R = self.get_rotation_matrix()
        return verts @ R.T + self.position

    def aabb(self) -> Tuple[np.ndarray, np.ndarray]:
        """World-space axis-aligned bounding box, computed from the actual
        transformed mesh vertices - correct for arbitrary rotation, scale,
        and asymmetric/hollow/custom geometry (not just boxes)."""
        verts = self.transformed_vertices()
        if len(verts) == 0:
            r = self.bounding_radius()
            he = vec3(r, r, r)
            return self.position - he, self.position + he
        return verts.min(axis=0), verts.max(axis=0)

    def bottom_y(self) -> float:
        """The lowest world-space Y coordinate of this body's actual
        geometry at its current position/orientation/scale. Used for both
        ground placement and the placement ghost (see place_on_ground) -
        there is exactly one implementation of "how low does this object
        currently reach", not a separate approximate one for previews."""
        return float(self.aabb()[0][1])

    def ground_clearance(self) -> float:
        """How far above a ground plane at world Y=0 this body's origin
        needs to sit for its lowest point to sit exactly on the ground, at
        the body's CURRENT orientation and scale (independent of its
        current position - translating a rigid mesh doesn't change the
        distance from its origin to its own lowest point)."""
        verts = self.mesh.vertices * self.scale
        R = self.get_rotation_matrix()
        local_lowest_y = float((verts @ R.T)[:, 1].min()) if len(verts) else 0.0
        return -local_lowest_y

    def place_on_ground(self, ground_y: float = 0.0) -> None:
        """Set this body's Y position so its actual (transformed) geometry
        rests exactly on a ground plane at ground_y, with zero penetration
        and zero gap - correct for any rotation, scale, or mesh shape. The
        placement ghost must call this exact same method (not a separate
        approximation) so the preview and the real spawn always agree."""
        self.position[1] = ground_y + self.ground_clearance()

    def half_height(self) -> float:
        """Half the world-space vertical extent of the transformed mesh -
        kept for callers that want a single "how tall is this, roughly"
        number; ground placement itself uses bottom_y()/place_on_ground(),
        not this, so it stays correct even when the mesh isn't symmetric
        about its own origin (e.g. a mug's floor sits above its base)."""
        lo, hi = self.aabb()
        return float((hi[1] - lo[1]) * 0.5)

    # ------------------------------------------------------------------
    # Integration
    # ------------------------------------------------------------------

    def apply_impulse(self, impulse: np.ndarray, contact_point: Optional[np.ndarray] = None) -> None:
        """Apply impulse at a contact point, generating both linear and angular response."""
        if self.is_static or self.inv_mass <= 0.0:
            return
        self.velocity += impulse * self.inv_mass
        self.wake()
        if contact_point is not None:
            r = contact_point - self.position
            torque_impulse = fast_cross3(r, impulse)
            # Use proper inertia tensor instead of sphere approximation
            inv_inertia_world = self.get_world_inv_inertia_tensor()
            delta_angular_velocity = inv_inertia_world @ torque_impulse
            self.angular_velocity += delta_angular_velocity

    def wake(self) -> None:
        self.is_asleep = False
        self.sleep_timer = 0.0

    def set_static(self, static: bool) -> None:
        """Switch this body between static (immovable, infinite effective
        mass) and dynamic.

        Must recompute the REAL mass from density*volume when turning a
        body dynamic again, not just the derived inv_mass - _update_mass_
        from_density() sets mass=0.0 as the static placeholder value, and
        that 0.0 previously stuck around forever after unstaticizing (only
        _update_inv_mass() was called, which just derives inv_mass from
        whatever self.mass currently is). The body would then still be
        affected by gravity in integrate() (which only checks is_static/
        is_asleep, not mass), but ground/body contact resolution could
        never push back against it (total inverse mass at the contact was
        always exactly 0, so _apply_point_contact bailed out immediately) -
        it would accelerate under gravity forever with nothing able to
        stop it, i.e. fall straight through the ground."""
        self.is_static = static
        self._update_mass_from_density()
        self._update_inertia_tensors()
        if static:
            self.velocity[:] = 0.0
            self.angular_velocity[:] = 0.0
            self.angular_velocity[:] = 0.0
            self.is_asleep = False
        else:
            self.wake()

    def integrate(self, dt: float, gravity: float, air_damping: float, angular_damping: float) -> None:
        if self.is_static or self.is_asleep:
            return
        self.velocity[0] *= air_damping
        self.velocity[2] *= air_damping
        self.velocity[1] -= gravity * dt
        self.angular_velocity *= angular_damping
        self.position += self.velocity * dt
        self.orientation = quat_integrate(self.orientation, self.angular_velocity, dt)

    def update_sleep_state(self, dt: float, lin_threshold: float, ang_threshold: float, time_required: float) -> None:
        if self.is_static:
            return
        speed = float(np.linalg.norm(self.velocity))
        ang_speed = float(np.linalg.norm(self.angular_velocity))
        if speed < lin_threshold and ang_speed < ang_threshold:
            self.sleep_timer += dt
            if self.sleep_timer >= time_required:
                self.is_asleep = True
                self.velocity[:] = 0.0
                self.angular_velocity[:] = 0.0
        else:
            self.sleep_timer = 0.0

    # ------------------------------------------------------------------
    # Shape accessors for collision
    # ------------------------------------------------------------------

    def get_scaled_half_extents(self) -> np.ndarray:
        """Half-extents of an oriented bounding box (OBB) in this body's own
        local space, scaled - generic for ANY shape (not just SHAPE_BOX).
        This is what lets the box-box/sphere-box collision routines in
        collision.py serve as a simple, general "collision representation"
        (per item 5 of the redesign: simple objects can have simple
        collision reps) for compound/mesh objects like the car or mug too,
        rather than falling back to an inaccurate bounding-sphere guess.
        It is NOT a substitute for real convex/GJK collision on genuinely
        non-box-like or concave geometry - just a much better default than
        a sphere for a boxy shape like a car body."""
        lo, hi = self.mesh.bounds
        return (hi - lo) * 0.5 * self.scale

    def get_obb_center_offset(self) -> np.ndarray:
        """Local-space offset from this body's origin to the center of its
        OBB (mesh.bounds midpoint), scaled. Zero for meshes centered on
        their own origin (all current primitives); non-zero for a mesh
        whose geometric center isn't at its local origin."""
        lo, hi = self.mesh.bounds
        return (hi + lo) * 0.5 * self.scale

    def get_scaled_radius(self) -> float:
        """Radius of the tightest origin-centred sphere containing this
        body's actual transformed geometry.

        Derived purely from mesh vertices - no shape-name lookup, no
        shape_params. For a sphere mesh this IS the exact radius (every
        vertex lies on the sphere by construction); for anything else it's
        the correct enclosing radius. That means it is equally meaningful
        for a primitive, a composite, or an arbitrary imported mesh, which
        the previous shape-name version was not: it silently returned a
        stale shape_params radius that had nothing to do with the real
        geometry for any object whose mesh wasn't literally that
        primitive.
        """
        return self.bounding_radius()

    def is_sphere_like(self, tolerance: float = 0.02) -> bool:
        """Whether this body's actual geometry is close enough to a sphere
        for the exact analytic sphere-sphere collision path to be valid.

        Measured from the mesh - every vertex roughly equidistant from the
        centroid, under uniform scale - rather than asked of a shape name.
        An imported ball, a procedurally generated sphere and a
        high-polygon user blob all answer honestly; a body merely *named*
        "sphere" whose mesh is something else does not get a wrong
        fast-path applied to it.
        """
        if not (self.scale[0] == self.scale[1] == self.scale[2]):
            return False  # non-uniform scale makes any sphere an ellipsoid
        verts = self.mesh.vertices
        if len(verts) < 4:
            return False
        radii = np.linalg.norm(verts - verts.mean(axis=0), axis=1)
        mean_r = float(radii.mean())
        if mean_r < 1e-9:
            return False
        return float(radii.std()) / mean_r < tolerance
