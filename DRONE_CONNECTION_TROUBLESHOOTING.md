# Drone Connection Troubleshooting

## Error: "Permission Denied COM5"

### What This Means:
Another program is currently using COM5, preventing your app from connecting.

### Most Common Causes:

#### 1. Mission Planner is Still Running
**Solution:**
```
1. Close Mission Planner completely
2. Check Task Manager (Ctrl+Shift+Esc)
3. Look for "MissionPlanner.exe" in Processes
4. If found, right-click → End Task
5. Restart your Drone Logbook app
```

#### 2. Your Diagnostic Script is Still Connected
**Solution:**
```
1. Close any Python windows running test_drone_download.py
2. Check Task Manager for python.exe processes
3. End any related to drone testing
4. Restart your Drone Logbook app
```

#### 3. Windows Has the Port Locked
**Solution:**
```
1. Unplug the USB cable from drone
2. Wait 5 seconds
3. Plug it back in
4. Try connecting again
```

#### 4. Another Instance of Your App is Running
**Solution:**
```
1. Close all browser windows with the app
2. Check Task Manager for python.exe
3. End the Drone Logbook process
4. Restart with START_LOGBOOK.bat
```

### Quick Fix Steps:

**Step 1: Close Everything**
```
1. Close Mission Planner
2. Close all Python windows
3. Close your Drone Logbook app
4. Unplug drone USB cable
```

**Step 2: Verify Port is Free**
```
1. Open Command Prompt
2. Run: mode
3. Should NOT see COM5 in use
```

**Step 3: Reconnect**
```
1. Plug in drone USB cable
2. Start Drone Logbook: START_LOGBOOK.bat
3. Go to Drone Connection tab
4. Click Auto-Detect
```

### Alternative: Use SD Card Method

If USB connection continues to have issues:

**Advantages:**
- ✅ No drivers needed
- ✅ No port conflicts
- ✅ Faster and more reliable
- ✅ Works every time

**Steps:**
```
1. Power off drone
2. Remove SD card
3. Insert SD card into computer
4. Copy all .BIN files to a folder
5. In app: Import Logs → Select folder
6. Done!
```

### Checking What's Using COM5:

**Method 1: Device Manager**
```
1. Win+X → Device Manager
2. Ports (COM & LPT)
3. Right-click COM5
4. Properties → Details → Device Instance Path
5. Shows which driver/program is using it
```

**Method 2: Command Line**
```powershell
# PowerShell command to check COM ports
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description, Status
```

### Why the Diagnostic Worked But App Doesn't:

The diagnostic script (`test_drone_download.py`) worked because:
1. It was the first to connect
2. It properly closed the connection when done
3. Nothing else was using the port at that time

Now the app can't connect because:
1. Something grabbed the port after the diagnostic
2. Most likely Mission Planner or another Python process
3. Windows hasn't released the port yet

### Prevention:

**Always close Mission Planner before using this app!**

Mission Planner and this app cannot use COM5 at the same time. You must:
1. Use Mission Planner for tuning/setup
2. Close Mission Planner completely
3. Then use this app for log management

### Still Having Issues?

**Try Manual Connection:**
```
1. In app, go to Drone Connection tab
2. Select "COM5" from dropdown
3. Select "57600" baud rate
4. Click "Connect" button
5. If it says "Permission Denied", something is still using the port
```

**Nuclear Option - Restart Computer:**
```
1. Close everything
2. Unplug drone
3. Restart computer
4. Plug in drone
5. Start ONLY the Drone Logbook app
6. Try connecting
```

### Recommended Workflow:

**For Flight Tuning:**
- Use Mission Planner

**For Log Management:**
- Close Mission Planner
- Use this app
- OR use SD card method (no conflicts!)

The SD card method is actually faster and more reliable for bulk log imports!