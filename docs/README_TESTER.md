# Print Order Web - Tester Guide

**Version**: 1.0 (Beta Test Package)
**Date**: December 2025
**Platform**: Windows 10/11 (64-bit)

---

## What is This?

Print Order Web is a browser-based application for submitting print jobs to a blockchain-enabled consumable tracking system. This test package allows you to evaluate the application's functionality and user experience.

**Architecture**: The application uses a fail-fast design that requires the ConsumableClient DLL for operation. There is no offline/demo mode - the blockchain API must be available.

---

## Quick Start (3 Steps)

### Step 1: Configure
1. Copy `.env.example` to `.env` (in the same folder as `PrintOrderWeb.exe`)
2. Edit `.env` with Notepad if needed (defaults should work)

### Step 2: Run
Double-click `PrintOrderWeb.exe`

**You should see:**
```
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

### Step 3: Access
Open your web browser and go to: **http://127.0.0.1:5000**

---

## Testing Workflow

### 1. Upload a PDF
- Go to http://127.0.0.1:5000
- Click "Upload PDF" or drag a PDF file
- Use any PDF file for testing

### 2. Enter Job Details
- **Quantity**: How many copies (limited by available media)
- **Color Mode**: Full color or black & white
- **Media Type**: Choose from available options
- **Print Quality**: Draft, Standard, or High

### 3. Review Estimates
- Check consumable usage estimates
- Verify inventory is sufficient

### 4. Submit Order
- Click "Submit Print Order"
- The job is submitted to the blockchain for processing
- Updated balances will reflect in the inventory sidebar

### 5. Confirmation
- View submission confirmation
- Start a new order if needed

---

## What to Test

### Core Functionality
- [ ] PDF upload works smoothly
- [ ] Inventory displays correctly in sidebar
- [ ] Quantity limits are enforced based on inventory
- [ ] Estimates calculate accurately
- [ ] Order submission succeeds
- [ ] Confirmation page displays properly
- [ ] "Start New Order" returns to beginning

### User Experience
- [ ] Instructions are clear
- [ ] Navigation is intuitive
- [ ] Error messages are helpful
- [ ] Loading states are visible
- [ ] Forms validate properly

### Edge Cases
- [ ] What happens with very large PDFs?
- [ ] What if quantity exceeds inventory?
- [ ] What if network is slow?
- [ ] Can you submit multiple orders in sequence?

---

## Known Issues

### Expected Behaviors (Not Bugs)
1. **Console window stays open**: Shows logs for debugging
2. **First load may be slow**: Flask and DLL are initializing
3. **Antivirus warnings**: May occur with PyInstaller executables (app is safe)

### Current Limitations
1. **Windows only**: ConsumableClient.dll is Windows-specific
2. **Single user**: No multi-user session management
3. **No job history**: Orders not saved between sessions
4. **DLL required**: Application will not start without the ConsumableClient DLL

---

## Troubleshooting

### Application won't start
**Solution**:
1. Verify `ConsumableClient.dll` is in the `_internal/` folder
2. Check for antivirus blocking the executable
3. Run as Administrator if needed

### "Module not found" errors
**Solution**: Restart the application. If persists, see TROUBLESHOOTING.md

### Browser shows "Connection refused"
**Solution**:
1. Check console shows "Running on http://127.0.0.1:5000"
2. Try http://localhost:5000 instead
3. Check firewall isn't blocking port 5000

### Order submission times out
**Solution**:
1. This can happen with blockchain network delays
2. Check your internet connection
3. Try again - blockchain may be busy

### "Insufficient inventory" error
**Solution**:
1. This is correct behavior when not enough consumables
2. Reduce quantity or wait for inventory to be replenished

---

## Providing Feedback

When reporting issues, please include:

1. **Steps to reproduce**: What did you do?
2. **Expected behavior**: What should happen?
3. **Actual behavior**: What actually happened?
4. **Screenshots**: If applicable
5. **Console logs**: Copy from the black console window
6. **Browser**: Chrome, Firefox, Edge, etc.
7. **PDF used**: Describe the file

### Feedback Template
```
Issue: [Brief description]

Steps:
1. [First step]
2. [Second step]
3. [What happened]

Expected: [What should happen]
Actual: [What actually happened]

Browser: [Chrome 120 / Firefox 121 / etc.]
PDF: [Description of file used]

Console output:
[Paste relevant logs here]

Screenshot: [Attach if helpful]
```

---

## Files Included

```
PrintOrderWeb/
├── PrintOrderWeb.exe          Main application
├── .env                       Configuration (copied from .env.example)
├── _internal/                 Bundled dependencies
│   ├── ConsumableClient.dll   Blockchain API library
│   ├── templates/             Web UI templates
│   ├── static/                CSS/JS assets
│   │   └── uploads/           PDF upload folder
│   └── translations/          Language files (EN/DE)
├── README_TESTER.md           This file
└── TROUBLESHOOTING.md         Detailed problem solving
```

---

## Technical Details

### Stack
- **Backend**: Flask (Python 3.11+)
- **Blockchain**: ConsumableClient API
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **PDF Analysis**: PyPDF library

### Architecture
- **Thread-per-job**: Each job submission runs in its own thread
- **Background inventory**: Refreshes every 30 seconds
- **Fail-fast**: Application requires DLL to start

### Network
- **Local only**: App runs on your computer (127.0.0.1)
- **Port**: 5000 (default Flask port)
- **No external hosting**: All processing is local

### Data Storage
- **Session-based**: Order data stored in browser session
- **No database**: Orders not persisted after completion
- **Cache**: 30-second inventory cache for performance

### Security
- **Local network**: Only accessible from your computer
- **HTTPS**: Not enabled (local testing only)
- **Authentication**: Not required (test build)

---

## Support

For questions or issues:
1. Check TROUBLESHOOTING.md first
2. Review console logs for error messages
3. Contact the development team with feedback

---

## Testing Checklist

Before reporting "everything works":

**Basic Flow**
- [ ] Application launches without errors
- [ ] Web interface loads in browser
- [ ] Inventory sidebar shows consumable balances
- [ ] Can upload a PDF file
- [ ] Can configure order settings
- [ ] Can submit an order
- [ ] Confirmation page shows results

**User Experience**
- [ ] Forms are intuitive
- [ ] Error messages are helpful
- [ ] Sidebar updates after submission
- [ ] Mobile view is usable

**Edge Cases**
- [ ] Handles insufficient inventory
- [ ] Validates quantity limits
- [ ] Shows errors gracefully

---

**Thank you for testing!**

Your feedback helps make this application better for everyone.
