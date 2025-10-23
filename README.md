# 🎬 VLC Ad Scheduler

**VLC Ad Scheduler** is a Python utility that automatically plays random ad breaks during video playback in VLC.  
It’s perfect for recreating the nostalgic TV or streaming experience — complete with real commercial breaks!

---

## ✨ Features

- 🎞️ Plays **random ad breaks** (2–3 minutes each)
- 📺 Supports **Show mode (10–12 min intervals)** and **Movie mode (15 min intervals)**
- 🎃 Includes themed **YouTube ad playlists by decade** (70s, 80s, 90s, 2000s, Halloween, Adult Swim)
- 💾 Supports **local ad videos** if placed in a folder (fallbacks to YouTube otherwise)
- 🔁 Randomly starts within videos for authentic mid-stream variety
- 🧠 Auto-detects when a new VLC playback session starts
- 🖥️ Includes an easy-to-use **Tkinter GUI**
- 🧰 Uses VLC’s HTTP interface to pause and resume media seamlessly

---

## 🧩 Requirements

- **Python 3.10+**
- **VLC Media Player** (must be installed)
- Python libraries:
  ```bash
  pip install psutil requests yt-dlp
  ```

---

## ⚙️ VLC Setup

1. Open **VLC → Tools → Preferences → Show All (bottom left)**
2. Go to:
   ```
   Interface → Main interfaces → Lua
   ```
3. Enable:
   ```
   Lua HTTP Interface
   ```
4. Set password to `ads`
5. Note the port number (default: `8080`)
6. Restart VLC

---

## 🏃‍♂️ Running the Script

1. Place this repository anywhere (e.g. `C:\vlcAds`)
2. Run:
   ```bash
   python vlc_ads_scheduler.py
   ```
3. The GUI will appear:
   - Select your **Ad Folder**
   - Choose **Decade**
   - Choose **Watching Type (Show or Movie)**
   - Set your **VLC path**, **port**, and **password**
   - Click **▶️ Start**

VLC will automatically pause when playback starts, play ads, then resume your show or movie.

---

## 📦 Folder Structure Example

```
C:\vlcAds\
│
├── nircmd.exe
├── vlc_ads_scheduler.py
├── README.md
└── Ad Folders\
    ├── ad1.mp4
    ├── ad2.mp4
    └── ...
```

---

## 📻 YouTube Playlists

The script automatically streams from curated decade-based YouTube playlists:

- 70s  
- 80s  
- 90s  
- 2000s  
- Halloween Seasoned Ads  
- Adult Swim Bumps and Commercials

You can edit or add playlists in the `YOUTUBE_PLAYLISTS` section inside the script.

---

## ⚠️ Notes

- You **must enable VLC’s web interface** for the script to control playback.
- If YouTube streams fail, update `yt-dlp`:
  ```bash
  yt-dlp -U
  ```
- Local videos take priority over YouTube playlists if detected.

---

## 💡 Tips

- Use **“Movie” mode** for long films (15-minute breaks).
- Use **“Show” mode** for episodic content (10–12-minute breaks).
- Place short custom ads in your folder for smoother transitions.
- Try themed playlists like **Halloween** for special events.

---

## 🧑‍💻 Author

Created by **Smash**  
For VR cinema and nostalgic TV streaming setups.
