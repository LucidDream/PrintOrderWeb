# Print Order Web - Troubleshooting Guide

This guide covers common issues and their solutions when testing Print Order Web.

---

## Application Won't Start

### Symptom: Double-clicking PrintOrderWeb.exe does nothing

**Possible Causes:**
1. Antivirus is blocking the executable
2. Missing Visual C++ Redistributables
3. File corruption during transfer

**Solutions:**

**Try 1: Check Antivirus**
```
1. Right-click PrintOrderWeb.exe
2. Select "Scan with Windows Security"
3. If flagged, add to exclusions:
   - Open Windows Security
   - Virus & threat protection
   - Manage settings
   - Exclusions > Add exclusion
   - Browse to PrintOrderWeb.exe
```

**Try 2: Run as Administrator**
```
1. Right-click PrintOrderWeb.exe
2. Select "Run as Administrator"
3. Allow when prompted
```

**Try 3: Install Visual C++ Redistributables**
```
Download from Microsoft:
https://aka.ms/vs/17/release/vc_redist.x64.exe

Install and restart computer
```

---

## Application Crashes on Startup

### Symptom: Console window opens briefly then closes

**Check Console Output:**
1. Open Command Prompt
2. Navigate to application folder
3. Run: `PrintOrderWeb.exe`
4. Read error message

**Common Errors:**

### "ImportError: DLL load failed"
**Cause**: Missing ConsumableClient.dll or wrong location
**Solution**:
```
1. Verify ConsumableClient.dll is in same folder as PrintOrderWeb.exe
2. Don't move files - keep folder structure intact
3. Re-extract from ZIP if needed
```

### "FileNotFoundError: .env"
**Cause**: Missing .env file
**Solution**:
```
1. Copy .env.example to .env
2. Must be in same folder as PrintOrderWeb.exe
3. Check file extension (not .env.txt)
```

### "Port 5000 is already in use"
**Cause**: Another application using port 5000
**Solution**:
```
Option 1: Stop other application
  - Check Task Manager for other Flask/Python apps
  - Close and try again

Option 2: Change port
  - Edit app.py (advanced)
  - Or kill process: taskkill /F /IM flask.exe
```

---

## Browser Connection Issues

### Symptom: "This site can't be reached" or "Connection refused"

**Solution 1: Verify Application is Running**
```
1. Check console window is open
2. Look for: "Running on http://127.0.0.1:5000"
3. If not visible, restart PrintOrderWeb.exe
```

**Solution 2: Try Alternative URLs**
```
Try these in order:
1. http://127.0.0.1:5000
2. http://localhost:5000
3. http://0.0.0.0:5000
```

**Solution 3: Check Firewall**
```
Windows Firewall:
1. Control Panel > Windows Defender Firewall
2. Advanced Settings > Inbound Rules
3. New Rule > Port > TCP > 5000
4. Allow the connection
5. Apply to all profiles
```

**Solution 4: Clear Browser Cache**
```
Chrome: Ctrl+Shift+Delete > Clear data
Firefox: Ctrl+Shift+Delete > Clear Now
Edge: Ctrl+Shift+Delete > Clear
```

---

## API Connection Problems

### Symptom: "⚠️ API Unavailable" warning in sidebar

**This is EXPECTED in Stub Mode**
- If `.env` has `ENABLE_API_MODE=false`, this is normal
- Stub mode intentionally shows empty inventory
- Switch to real API mode for live data

**If Using Real API Mode (ENABLE_API_MODE=true):**

**Check 1: DLL Present**
```
1. Verify ConsumableClient.dll exists
2. Must be in same folder as PrintOrderWeb.exe
3. File size should be ~500KB-2MB
4. Don't rename or move it
```

**Check 2: DLL Path in Config**
```
1. Open .env file
2. Check: CONSUMABLE_DLL_PATH=./ConsumableClient.dll
3. Should be relative path
4. Or use absolute: C:\Path\To\ConsumableClient.dll
```

**Check 3: Windows Permissions**
```
1. Right-click ConsumableClient.dll
2. Properties > Security
3. Ensure "Read" and "Read & execute" are checked
4. Unblock if prompted (Properties > General > Unblock)
```

**Check 4: Console Logs**
```
Look for error messages like:
  - "DLL not found"
  - "Failed to initialize API"
  - "Not implemented"

If "Not implemented": Blockchain/network issue, not app issue
```

---

## Order Submission Failures

### Symptom: "Job submission failed" error

**Error: "Insufficient inventory"**
```
Cause: Not enough consumables
Solution:
  1. This is CORRECT behavior
  2. Reduce quantity
  3. Or check real inventory levels
  4. In stub mode, inventory is empty by design
```

**Error: "Timeout after 60 seconds"**
```
Cause: Blockchain is slow or unavailable
Solution:
  1. Check internet connection
  2. Try again (network may be busy)
  3. Reduce complexity (fewer colors/pages)
  4. Wait a few minutes and retry
```

**Error: "Invalid job payload"**
```
Cause: Malformed data sent to API
Solution:
  1. Refresh page (F5)
  2. Start new order from scratch
  3. If persists, report as bug with:
     - Console logs
     - PDF used
     - Settings chosen
```

**Error: "API returned null"**
```
Cause: ConsumableClient.dll issue
Solution:
  1. Restart application
  2. Try stub mode first
  3. Check DLL is correct version (v2.0.0.1)
  4. May be temporary blockchain issue
```

---

## PDF Upload Issues

### Symptom: "Invalid file type" error

**Solution:**
```
1. Only PDF files supported
2. Check file extension is .pdf (not .PDF.pdf)
3. File must be valid PDF (not renamed Word doc)
4. Try sample PDFs first to isolate issue
```

### Symptom: Upload hangs or times out

**Solution:**
```
1. File size limit: Recommended < 10 MB
2. Large files may take time
3. Complex PDFs may slow analysis
4. Try simpler PDF first
5. Check console for errors
```

### Symptom: "Failed to analyze PDF"

**Solution:**
```
1. PDF may be corrupted
2. PDF may be password-protected
3. PDF may have unusual formatting
4. Try sample PDFs to verify app works
5. Try different PDF
```

---

## UI/Display Issues

### Symptom: Page layout is broken

**Solution:**
```
1. Clear browser cache
2. Refresh page (Ctrl+F5 / Cmd+Shift+R)
3. Try different browser
4. Check console for 404 errors (missing CSS/JS)
```

### Symptom: Inventory sidebar empty

**If in Stub Mode:**
```
This is EXPECTED - stub returns no data
Switch to ENABLE_API_MODE=true for real data
```

**If in Real API Mode:**
```
1. Check "API Unavailable" warning
2. See API Connection Problems section above
3. Refresh sidebar (auto-refreshes every 30s)
```

### Symptom: Estimates show 0.0 for all inks

**Solution:**
```
1. If quantity = 0, estimates will be 0 (correct)
2. If black & white mode, color inks = 0 (correct)
3. If color mode and all 0, refresh page
4. Check console for estimation errors
```

---

## Performance Issues

### Symptom: Application is slow or unresponsive

**Check 1: System Resources**
```
1. Open Task Manager
2. Check CPU/Memory usage
3. Close other applications
4. Restart computer if needed
```

**Check 2: Network Issues**
```
If using Real API Mode:
1. Blockchain calls can be slow
2. First call always slower (initialization)
3. 30-second cache reduces subsequent calls
4. Slow internet = slow blockchain
```

**Check 3: PDF Complexity**
```
1. Large PDFs take longer to analyze
2. Many pages = slower processing
3. High-resolution images slow down upload
4. Try simpler PDF first
```

---

## Error Message Reference

### "No module named 'flask'"
**Cause**: PyInstaller bundle incomplete
**Solution**: Re-extract from ZIP, don't copy individual files

### "Template not found"
**Cause**: Missing templates folder
**Solution**: Keep folder structure intact, don't move files

### "Static file not found (404)"
**Cause**: Missing static assets
**Solution**: Ensure static/ folder is present

### "Session expired, please refresh"
**Cause**: Browser session timed out
**Solution**: Refresh page (F5), normal behavior

### "CSRF token missing"
**Cause**: Session/cookie issue
**Solution**: Clear cookies, restart browser

### "Server Error (500)"
**Cause**: Unhandled exception in app
**Solution**: Check console logs, report with steps to reproduce

---

## Data & Privacy

### Where is data stored?

**Session Data:**
- Stored in browser session (RAM only)
- Cleared when browser closes
- Not written to disk

**Uploaded PDFs:**
- Temporarily stored in uploads/ folder
- Deleted after session ends
- Not transmitted anywhere except analysis

**Configuration:**
- Stored in .env file (plain text)
- Contains no sensitive data by default
- Keep blockchain keys secure if added

### Is data sent to external servers?

**Stub Mode:**
- No external connections
- Everything runs locally

**Real API Mode:**
- ConsumableClient.dll connects to blockchain
- PDF file stays local (not uploaded)
- Only transaction data sent to blockchain
- No analytics or telemetry

---

## Reporting Bugs

When you find a bug, please include:

### Required Information
1. **Steps to reproduce**: Exact sequence of actions
2. **Expected result**: What should happen
3. **Actual result**: What actually happened
4. **Mode**: Stub or Real API
5. **Browser**: Name and version
6. **PDF**: Which file (or "custom")

### Helpful Information
7. **Console logs**: Copy from black window
8. **Screenshot**: If UI issue
9. **Error message**: Exact text
10. **Frequency**: Always, sometimes, once

### Example Bug Report
```
ISSUE: Order submission hangs at 75%

STEPS:
1. Uploaded business_card.pdf
2. Set quantity to 100
3. Selected ProMatte A4
4. Clicked Submit
5. Progress bar stuck at 75% for 5+ minutes

EXPECTED: Order completes in ~30 seconds
ACTUAL: Hangs indefinitely at 75%

MODE: Real API (ENABLE_API_MODE=true)
BROWSER: Chrome 120.0.6099.129
PDF: sample_pdfs/business_card.pdf
FREQUENCY: Happened 3/3 times

CONSOLE OUTPUT:
[2025-11-13 10:15:32] Submitting job to blockchain
[2025-11-13 10:15:33] Job handle: 12345
[2025-11-13 10:15:35] Polling status...
[ERROR] Timeout waiting for job completion

SCREENSHOT: [attached]
```

---

## Advanced Troubleshooting

### Enable Debug Logging

**Edit .env:**
```
FLASK_DEBUG=1
```

**Restart application**

**Console will show verbose logs:**
- All HTTP requests
- Template rendering
- API calls
- Cache operations

### Check Application Logs

**If application creates log files:**
```
Location: Same folder as PrintOrderWeb.exe
Files: *.log
View with: Notepad
```

### Network Traffic Inspection

**Use browser DevTools:**
```
1. F12 (Chrome/Edge) or Ctrl+Shift+I (Firefox)
2. Network tab
3. Reload page
4. Check for failed requests (red)
5. Look for 404, 500 errors
```

### Manual DLL Testing

**Test ConsumableClient.dll:**
```python
# In Python console (if installed)
import ctypes
dll = ctypes.CDLL('./ConsumableClient.dll')
print("DLL loaded successfully")
```

---

## Still Having Issues?

If this guide doesn't solve your problem:

1. **Check README_TESTER.md**: May have additional info
2. **Review Console Logs**: Often reveals root cause
3. **Try Sample PDFs**: Isolate whether issue is with your PDF
4. **Test in Stub Mode**: Isolate whether issue is blockchain-related
5. **Contact Support**: Provide all information from "Reporting Bugs"

---

## Appendix: Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 500 | Server error | Check console logs |
| 404 | File not found | Keep folder structure intact |
| 400 | Bad request | Check form validation |
| 503 | Service unavailable | API/blockchain down |
| ERR_CONNECTION_REFUSED | Can't connect | Check app is running |
| CORS error | Cross-origin block | Use correct URL (127.0.0.1) |

---

**Last Updated**: November 2025
