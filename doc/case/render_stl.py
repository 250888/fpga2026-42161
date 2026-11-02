"""把二进制 STL 渲染成着色 PNG（numpy z-buffer，无外部渲染器依赖）。"""
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load_stl(path: Path):
    data = path.read_bytes()
    n = struct.unpack("<I", data[80:84])[0]
    tris = np.frombuffer(data[84:84 + n * 50], dtype=np.uint8)
    tris = tris.reshape(n, 50)[:, 12:48].copy()      # 跳过法线与属性
    v = tris.view("<f4").reshape(n, 3, 3).astype(np.float64)
    return v


def render(v: np.ndarray, out: Path, size=1500, bg=(14, 19, 25)):
    # --- 姿态：等轴测 ---
    az, el = np.deg2rad(-38), np.deg2rad(26)
    Rz = np.array([[np.cos(az), -np.sin(az), 0],
                   [np.sin(az),  np.cos(az), 0],
                   [0, 0, 1]])
    Rx = np.array([[1, 0, 0],
                   [0, np.cos(el), -np.sin(el)],
                   [0, np.sin(el),  np.cos(el)]])
    R = Rx @ Rz
    p = v @ R.T

    lo, hi = p.reshape(-1, 3).min(0), p.reshape(-1, 3).max(0)
    span = (hi - lo)[:2]
    scale = (size * 0.86) / max(span)
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    W = H = size
    sx = (p[:, :, 0] - cx) * scale + W / 2
    sy = -(p[:, :, 1] - cy) * scale + H / 2      # y 翻转
    sz = p[:, :, 2]

    # --- 面法线（世界坐标）---
    nrm = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    nrm /= ln
    # 背面剔除（相机看向 -Z 后的转换系里，法线朝观察者）
    nview = nrm @ R.T
    vis = nview[:, 2] > 0
    if not vis.any():
        vis = np.ones(len(nrm), bool)

    # --- 光照 ---
    L1 = np.array([0.35, 0.55, 0.76]); L1 /= np.linalg.norm(L1)
    L2 = np.array([-0.5, -0.2, 0.84]); L2 /= np.linalg.norm(L2)
    lam = np.clip(nrm @ L1, 0, 1) * 0.78 + np.clip(nrm @ L2, 0, 1) * 0.22
    shade = 0.16 + 0.84 * lam

    IMG = np.zeros((H, W, 3), np.float64)
    IMG[:] = np.array(bg) / 255.0
    ZB = np.full((H, W), -1e18)

    for i in np.nonzero(vis)[0]:
        x, y, z = sx[i], sy[i], sz[i]
        shade_i = shade[i]
        color = np.array([0.62, 0.70, 0.80]) * shade_i
        color = np.clip(color, 0, 1)
        x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max()))
        y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max()))
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W - 1), min(y1, H - 1)
        if x1 <= x0 or y1 <= y0:
            continue
        Xg, Yg = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        d = ((y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2]))
        if abs(d) < 1e-12:
            continue
        a = ((y[1] - y[2]) * (Xg - x[2]) + (x[2] - x[1]) * (Yg - y[2])) / d
        b = ((y[2] - y[0]) * (Xg - x[2]) + (x[0] - x[2]) * (Yg - y[2])) / d
        c = 1 - a - b
        m = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
        if not m.any():
            continue
        zz = a * z[0] + b * z[1] + c * z[2]
        sub_z = ZB[y0:y1 + 1, x0:x1 + 1]
        upd = m & (zz > sub_z)
        if not upd.any():
            continue
        sub_z[upd] = zz[upd]
        sub_c = IMG[y0:y1 + 1, x0:x1 + 1]
        sub_c[upd] = color

    img = (np.clip(IMG, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(img).save(out)
    return out


if __name__ == "__main__":
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    render(load_stl(src), dst)
    print("wrote", dst, dst.stat().st_size)
