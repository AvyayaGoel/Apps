"""
gpu_renderer.py - ModernGL-based GPU rendering of generic mesh data.

This replaces immediate-mode drawing (glBegin/glVertex per triangle, every
frame, for every object) with a real GPU pipeline: each distinct mesh is
uploaded ONCE into a vertex buffer + index buffer + VAO, and thereafter
drawn with a single draw call per object. Per-object variation
(position/orientation/scale/color/alpha) is passed as uniforms, so two
hundred cars share one uploaded mesh and cost two hundred draw calls
rather than two hundred re-tessellations.

Design notes:

- The renderer consumes GENERIC mesh data (`mesh.Mesh`: vertices, faces,
  normals, optional per-vertex colors). It contains no per-object
  branching whatsoever - no "if this is a car" path. Anything that can
  produce a Mesh (a primitive generator, a JSON parts recipe, an imported
  OBJ/STL, a future curve-based or user-authored generator) renders here
  unchanged.

- Meshes are cached by identity (`id(mesh)`) AND kept alive via a strong
  reference in the cache, so the id can't be recycled by the garbage
  collector onto a different object while we still hold GPU buffers for
  it (a real, nasty class of bug when caching on id alone). Since
  `mesh.get_mesh_by_kind` already returns one shared, immutable Mesh
  instance per object kind, this means one GPU upload per kind.

- Per-vertex colors use a NaN sentinel for "no override" (see Mesh.colors)
  which can't be fed to GLSL directly, so it's resolved at upload time
  into a parallel `has_color` attribute; the shader then mixes between
  the object's base color uniform and the baked vertex color. That keeps
  the "most of this object uses its spawn color, but these specific parts
  are always dark" case working without needing a separate draw call or a
  separate mesh per color.

- Lighting is a simple single directional light with ambient + Lambert
  diffuse, matching what the legacy fixed-function path produced closely
  enough that the visual result doesn't jump when switching pipelines.
"""
from __future__ import annotations

import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)

try:
    import moderngl
except ImportError:  # pragma: no cover - exercised only on systems without moderngl
    moderngl = None

VERTEX_SHADER = """
#version 330

uniform mat4 u_mvp;
uniform mat4 u_model;
uniform mat3 u_normal_mat;

in vec3 in_position;
in vec3 in_normal;
in vec3 in_color;
in float in_has_color;

out vec3 v_normal;
out vec3 v_color;
out float v_has_color;

void main() {
    gl_Position = u_mvp * vec4(in_position, 1.0);
    v_normal = normalize(u_normal_mat * in_normal);
    v_color = in_color;
    v_has_color = in_has_color;
}
"""

FRAGMENT_SHADER = """
#version 330

uniform vec3 u_base_color;
uniform vec3 u_light_dir;
uniform float u_ambient;
uniform float u_alpha;

in vec3 v_normal;
in vec3 v_color;
in float v_has_color;

out vec4 f_color;

void main() {
    vec3 base = mix(u_base_color, v_color, v_has_color);
    vec3 n = normalize(v_normal);
    // Two-sided lighting: a closed mesh viewed from inside (or a thin
    // open surface like a mug's inner wall) should still be lit rather
    // than going black, which is what a one-sided dot() would do.
    float diffuse = abs(dot(n, normalize(-u_light_dir)));
    float lighting = clamp(u_ambient + (1.0 - u_ambient) * diffuse, 0.0, 1.0);
    f_color = vec4(base * lighting, u_alpha);
}
"""


# ---------------------------------------------------------------------------
# Matrix helpers (row-major / "v' = M @ v" convention, transposed on upload
# because GLSL mat4 is column-major).
# ---------------------------------------------------------------------------

def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov_deg) * 0.5)
    aspect = aspect if aspect > 1e-6 else 1.0
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    up = np.asarray(up, dtype=np.float64)

    forward = target - eye
    norm = np.linalg.norm(forward)
    forward = forward / norm if norm > 1e-12 else np.array([0.0, 0.0, -1.0])

    side = np.cross(forward, up)
    norm = np.linalg.norm(side)
    # Guard the degenerate case where the view direction is parallel to
    # `up` (looking straight down/up), which would otherwise produce a
    # zero-length side vector and a matrix full of NaNs.
    if norm < 1e-9:
        fallback = np.array([0.0, 0.0, 1.0]) if abs(forward[1]) > 0.9 else np.array([0.0, 1.0, 0.0])
        side = np.cross(forward, fallback)
        norm = np.linalg.norm(side)
    side = side / norm

    true_up = np.cross(side, forward)

    m = np.eye(4, dtype=np.float64)
    m[0, :3] = side
    m[1, :3] = true_up
    m[2, :3] = -forward
    m[0, 3] = -np.dot(side, eye)
    m[1, 3] = -np.dot(true_up, eye)
    m[2, 3] = np.dot(forward, eye)
    return m


def model_matrix(position: np.ndarray, rotation_3x3: np.ndarray, scale: np.ndarray) -> np.ndarray:
    m = np.eye(4, dtype=np.float64)
    m[:3, :3] = rotation_3x3 * np.asarray(scale, dtype=np.float64)  # column-wise scale
    m[:3, 3] = position
    return m


def normal_matrix(model: np.ndarray) -> np.ndarray:
    """Inverse-transpose of the model matrix's 3x3 part - required so that
    normals stay perpendicular to surfaces under NON-UNIFORM scaling
    (which this engine supports per-axis, so simply reusing the rotation
    would visibly mis-light any stretched object)."""
    upper = model[:3, :3]
    try:
        return np.linalg.inv(upper).T
    except np.linalg.LinAlgError:
        return np.eye(3, dtype=np.float64)


class _UploadedMesh:
    __slots__ = ("vbo", "ibo", "vao", "index_count", "mesh_ref")

    def __init__(self, vbo, ibo, vao, index_count, mesh_ref):
        self.vbo = vbo
        self.ibo = ibo
        self.vao = vao
        self.index_count = index_count
        self.mesh_ref = mesh_ref

    def release(self) -> None:
        for resource in (self.vao, self.ibo, self.vbo):
            try:
                resource.release()
            except Exception:
                pass


class GPUMeshRenderer:
    """Uploads and draws `mesh.Mesh` objects through a ModernGL pipeline."""

    def __init__(self, ctx=None) -> None:
        if moderngl is None:
            raise RuntimeError("moderngl is not installed")
        # attach to the OpenGL context Qt already created for the widget
        self.ctx = ctx if ctx is not None else moderngl.create_context()
        self.program = self.ctx.program(
            vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER
        )
        self._cache: Dict[int, _UploadedMesh] = {}
        self._proj = np.eye(4)
        self._view = np.eye(4)
        self.light_dir = np.array([-0.4, -1.0, -0.35], dtype=np.float64)
        self.ambient = 0.35

    # -- frame setup --------------------------------------------------

    def set_camera(self, proj: np.ndarray, view: np.ndarray) -> None:
        self._proj = proj
        self._view = view

    def set_light(self, direction: np.ndarray, ambient: float) -> None:
        self.light_dir = np.asarray(direction, dtype=np.float64)
        self.ambient = float(ambient)

    # -- mesh upload / cache ------------------------------------------

    def upload(self, mesh) -> _UploadedMesh:
        key = id(mesh)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        faces = np.asarray(mesh.faces, dtype=np.int32)
        normals = mesh.normals
        if len(normals) != len(vertices):
            normals = np.zeros_like(vertices)
        normals = np.asarray(normals, dtype=np.float32)

        # Resolve the NaN "no override" sentinel into an explicit flag the
        # shader can mix on (GLSL has no usable NaN semantics here).
        colors = np.zeros_like(vertices)
        has_color = np.zeros((len(vertices), 1), dtype=np.float32)
        if len(mesh.colors) == len(vertices) and len(vertices) > 0:
            raw = np.asarray(mesh.colors, dtype=np.float32)
            valid = ~np.isnan(raw[:, 0])
            colors[valid] = raw[valid]
            has_color[valid, 0] = 1.0

        interleaved = np.hstack([vertices, normals, colors, has_color]).astype("f4")
        vbo = self.ctx.buffer(interleaved.tobytes())
        ibo = self.ctx.buffer(faces.astype("i4").tobytes())
        vao = self.ctx.vertex_array(
            self.program,
            [(vbo, "3f 3f 3f 1f", "in_position", "in_normal", "in_color", "in_has_color")],
            ibo,
            index_element_size=4,
        )
        uploaded = _UploadedMesh(vbo, ibo, vao, faces.size, mesh)
        self._cache[key] = uploaded
        return uploaded

    def invalidate(self, mesh=None) -> None:
        """Drop cached GPU buffers - for a single mesh, or all of them."""
        if mesh is None:
            for uploaded in self._cache.values():
                uploaded.release()
            self._cache.clear()
        else:
            uploaded = self._cache.pop(id(mesh), None)
            if uploaded is not None:
                uploaded.release()

    @property
    def cached_mesh_count(self) -> int:
        return len(self._cache)

    # -- drawing ------------------------------------------------------

    def _set_uniform(self, name: str, value) -> None:
        """Set a uniform if the shader actually has it. GLSL compilers
        strip uniforms that don't affect the output, so a uniform declared
        in the source may legitimately not exist in the linked program
        (u_model is currently only needed if/when the fragment shader does
        world-space lighting) - writing to it blindly raises KeyError."""
        member = self.program.get(name, None)
        if member is None:
            return
        if isinstance(value, (bytes, bytearray, memoryview)):
            member.write(value)
        else:
            member.value = value

    def draw(self, mesh, position, rotation_3x3, scale, color, alpha: float = 1.0) -> None:
        if len(mesh.faces) == 0:
            return
        uploaded = self.upload(mesh)

        model = model_matrix(position, rotation_3x3, scale)
        mvp = self._proj @ self._view @ model

        # GLSL matrices are column-major; our matrices are built row-major
        # (v' = M @ v), so they're transposed on the way to the GPU.
        self._set_uniform("u_mvp", np.ascontiguousarray(mvp.T, dtype="f4").tobytes())
        self._set_uniform("u_model", np.ascontiguousarray(model.T, dtype="f4").tobytes())
        self._set_uniform(
            "u_normal_mat", np.ascontiguousarray(normal_matrix(model).T, dtype="f4").tobytes()
        )
        self._set_uniform("u_base_color", tuple(float(c) for c in color[:3]))
        self._set_uniform("u_light_dir", tuple(float(c) for c in self.light_dir))
        self._set_uniform("u_ambient", float(self.ambient))
        self._set_uniform("u_alpha", float(alpha))

        uploaded.vao.render(moderngl.TRIANGLES)

    def release(self) -> None:
        self.invalidate()
        try:
            self.program.release()
        except Exception:
            pass
