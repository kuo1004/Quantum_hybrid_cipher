import numpy as np
import cv2
import matplotlib.pyplot as plt
from skimage.metrics import structural_similarity as ssim
from scipy.stats import entropy
import pandas as pd
from PIL import Image
# === Function definitions ===
def calculate_entropy(img):
    histogram, _ = np.histogram(img.ravel(), bins=256, range=(0, 256), density=True)
    return entropy(histogram + 1e-10)

def calculate_npcr_uaci(img1, img2):
    diff = img1 != img2
    npcr = np.sum(diff) / diff.size
    uaci = np.sum(np.abs(img1.astype(np.int32) - img2.astype(np.int32))) / (255 * diff.size)
    return npcr, uaci

def calculate_psnr(img1, img2):
    mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
    if mse == 0:
        return float('inf')
    return 20 * np.log10(255.0 / np.sqrt(mse))

# === Load images ===
input_img = cv2.imread('input.png', cv2.IMREAD_GRAYSCALE)
encrypted_img = cv2.imread('cipher.png', cv2.IMREAD_GRAYSCALE)
stego_img = cv2.imread('stego.png', cv2.IMREAD_GRAYSCALE)
decrypted_img = cv2.imread('decrypted.png', cv2.IMREAD_GRAYSCALE)

if input_img is None or encrypted_img is None or stego_img is None:
    print("圖片讀取失敗")
    exit()

# === 分析 ===
results = {}

# AES 階段（input -> encrypted）
results['ogi v.s AES'] = {
    'NPCR': calculate_npcr_uaci(input_img, encrypted_img)[0],
    'UACI': calculate_npcr_uaci(input_img, encrypted_img)[1],
    'PSNR': calculate_psnr(input_img, encrypted_img),
    'SSIM': ssim(input_img, encrypted_img)
}

results['ogi v.s LSB'] = {
    'NPCR': calculate_npcr_uaci(input_img, stego_img)[0],
    'UACI': calculate_npcr_uaci(input_img, stego_img)[1],
    'PSNR': calculate_psnr(input_img, stego_img),
    'SSIM': ssim(input_img, stego_img)
}


# LSB 階段（encrypted -> stego）
results['AES v.s LSB'] = {
    'NPCR': calculate_npcr_uaci(encrypted_img, stego_img)[0],
    'UACI': calculate_npcr_uaci(encrypted_img, stego_img)[1],
    'PSNR': calculate_psnr(encrypted_img, stego_img),
    'SSIM': ssim(encrypted_img, stego_img)
}
'''
results['ogi v.s decrypted'] = {
    'NPCR': calculate_npcr_uaci(input_img, decrypted_img)[0],
    'UACI': calculate_npcr_uaci(input_img, decrypted_img)[1],
    'PSNR': calculate_psnr(input_img, decrypted_img),
    'SSIM': ssim(input_img, decrypted_img)
}
'''
# === 顯示 DataFrame ===
df = pd.DataFrame(results).T
print("\n分析結果：\n")
print(df.round(6))


original_img = Image.open("input.png").convert("RGB")
recovered_img = Image.open("decrypted.png").convert("RGB")
stego_img = Image.open("stego.png").convert("RGB")


# 轉成 NumPy array
original_arr = np.array(original_img)
recovered_arr = np.array(recovered_img)
stego_arr = np.array(stego_img)

# --- 比對是否完全一致（逐像素 RGB） ---
if np.array_equal(original_arr, recovered_arr):
    print("✅RGB三通道完美一致")
else:
    print("❌RGB有差異")

# --- 繪製每個通道的直方圖比較 ---
colors = ('red', 'green', 'blue')
channel_labels = ('Red Channel', 'Green Channel', 'Blue Channel')

plt.figure(figsize=(15, 5))

for i, color in enumerate(colors):
    hist_original = np.histogram(original_arr[:, :, i], bins=256, range=(0, 256))[0]
    hist_recovered = np.histogram(recovered_arr[:, :, i], bins=256, range=(0, 256))[0]
    hist_stego = np.histogram(stego_arr[:, :, i], bins=256, range=(0, 256))[0]
    
    plt.subplot(1, 3, i+1)
    plt.plot(hist_original, color=color, label='Original')
    plt.plot(hist_recovered, color='black', linestyle='dashed', label='Decrypted')
    plt.plot(hist_stego, color='yellow', linestyle='dashed', label='stego')
    plt.title(channel_labels[i])
    plt.xlabel('Pixel Intensity')
    plt.ylabel('Pixel Count')
    plt.legend()

plt.tight_layout()
plt.show()
