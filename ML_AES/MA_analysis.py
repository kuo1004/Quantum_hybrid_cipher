import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

def load_gray(path):
    """讀取影像並轉為灰階矩陣"""
    img = Image.open(path).convert("L")
    return np.array(img, dtype=np.uint8)

def calc_entropy(arr):
    """計算灰階影像的資訊熵（位元）"""
    hist, _ = np.histogram(arr.flatten(), bins=256, range=(0, 255))
    p = hist / hist.sum()
    p = p[p > 0]
    return -np.sum(p * np.log2(p))

def calc_corr(arr):
    """計算水平相鄰像素的相關係數"""
    x = arr[:, :-1].flatten().astype(np.int32)
    y = arr[:, 1:].flatten().astype(np.int32)
    return np.corrcoef(x, y)[0, 1]

def plot_hist(arr, title):
    """畫灰階直方圖"""
    plt.figure(figsize=(5, 4))
    plt.title(title)
    plt.hist(arr.flatten(), bins=256, range=(0, 255), alpha=0.7)
    plt.xlabel("Gray scale")
    plt.ylabel("pixel scale")
    plt.tight_layout()

def main():
    # 讀取三張影像
    orig    = load_gray("input.png")
    aes_img = load_gray("cipher.png")
    hyb_img = load_gray("MAencrypted.png")

    # 計算統計值
    e0, c0 = calc_entropy(orig),    calc_corr(orig)
    e1, c1 = calc_entropy(aes_img), calc_corr(aes_img)
    e2, c2 = calc_entropy(hyb_img), calc_corr(hyb_img)

    # 畫直方圖
    plot_hist(orig,    f"original    entropy={e0:.3f}, Corr={c0:.3f}")
    plot_hist(aes_img, f"AES    entropy={e1:.3f}, Corr={c1:.3f}")
    plot_hist(hyb_img, f"ML-KEM+AES   entropy={e2:.3f}, Corr={c2:.3f}")

    # 列印比較結果
    print("=== 資訊熵 (bits) ===")
    print(f"原圖: {e0:.4f}    AES: {e1:.4f}    混合後量子: {e2:.4f}\n")
    print("=== 水平相鄰像素相關係數 ===")
    print(f"原圖: {c0:.4f}    AES: {c1:.4f}    混合後量子: {c2:.4f}")

    plt.show()

if __name__ == "__main__":
    main()
