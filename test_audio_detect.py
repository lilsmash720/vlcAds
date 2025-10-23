from pycaw.pycaw import AudioUtilities

print("🎧 Listing all audio sessions:")
sessions = AudioUtilities.GetAllSessions()
for session in sessions:
    if session.Process:
        print(f"- {session.Process.name()} | State: {session.State}")
