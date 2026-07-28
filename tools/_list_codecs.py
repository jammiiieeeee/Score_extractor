import cv2, glob, os

for path in sorted(glob.glob("yt_dl/*.mp4")):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        continue
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join([chr((fourcc >> 8*i) & 0xFF) for i in range(4)])
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    mb = os.path.getsize(path) / (1024*1024)
    cap.release()
    print(f"{os.path.basename(path):45s} {codec:6s} {w}x{h} {fps:5.0f}fps {frames:6d}fr {mb:6.1f}MB")
