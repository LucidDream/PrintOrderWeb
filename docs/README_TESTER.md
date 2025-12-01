# Print Order Web - Tester Guide

**Version**: 1.0 (Beta Test Package)
**Date**: November 2025
**Platform**: Windows 10/11 (64-bit)

---

## What is This?

Print Order Web is a browser-based application for submitting print jobs to a blockchain-enabled consumable tracking system. This test package allows you to evaluate the application's functionality and user experience.

---

## Quick Start (3 Steps)

### Step 1: Configure
1. Copy `.env.example` to `.env` (in the same folder as `PrintOrderWeb.exe`)
2. Edit `.env` with Notepad
3. Set `ENABLE_API_MODE=true` for real blockchain testing (or leave as `false` for demo mode)

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

## Two Testing Modes

### Stub Mode (Demo/Offline)
- **Setting**: `ENABLE_API_MODE=false` in `.env`
- **What it does**: Simulates blockchain operations without actual transactions
- **Use when**: Testing UI/UX, no blockchain access needed
- **Inventory**: Shows empty inventory (design choice to force real API use)

### Real API Mode (Live Blockchain)
- **Setting**: `ENABLE_API_MODE=true` in `.env`
- **What it does**: Connects to actual blockchain, submits real transactions
- **Use when**: Full integration testing
- **Requires**: ConsumableClient.dll (included) and blockchain access
- **Inventory**: Shows live consumable balances from blockchain

---

## Testing Workflow

### 1. Upload a PDF
- Go to http://127.0.0.1:5000
- Click "Upload PDF" or drag a PDF file
- Sample PDFs are provided in `sample_pdfs/` folder

### 2. Enter Job Details
- **Quantity**: How many copies (limited by available media)
- **Color Mode**: Full color or black & white
- **Media Type**: Choose from available options
- **Print Quality**: Draft, Standard, or High

### 3. Review Estimates
- Check consumable usage estimates
- Verify inventory is sufficient
- Review AI reasoning (if available)

### 4. Submit Order
- Click "Submit Print Order"
- Watch real-time progress updates
- Wait for blockchain confirmation (~15-30 seconds)

### 5. Confirmation
- View transaction IDs
- Check updated inventory balances
- Download receipt (optional)

---

## What to Test

### Core Functionality
- [ ] PDF upload works smoothly
- [ ] Inventory displays correctly
- [ ] Quantity limits are enforced
- [ ] Estimates calculate accurately
- [ ] Order submission succeeds
- [ ] Progress updates appear
- [ ] Confirmation page shows all details
- [ ] Updated inventory reflects changes

### User Experience
- [ ] Instructions are clear
- [ ] Navigation is intuitive
- [ ] Error messages are helpful
- [ ] Loading states are visible
- [ ] Forms validate properly
- [ ] Mobile responsiveness (test on phone/tablet)

### Edge Cases
- [ ] What happens with very large PDFs?
- [ ] What if quantity exceeds inventory?
- [ ] What if API is unavailable?
- [ ] What if network is slow?
- [ ] Can you submit multiple orders in sequence?

---

## Known Issues

### Expected Behaviors (Not Bugs)
1. **Stub mode shows empty inventory**: By design - forces use of real API for actual data
2. **Console window stays open**: Shows logs for debugging
3. **First load may be slow**: Flask is initializing
4. **Antivirus warnings**: May occur with PyInstaller executables (app is safe)

### Current Limitations
1. **Windows only**: ConsumableClient.dll is Windows-specific
2. **Single user**: No multi-user session management yet
3. **No job history**: Orders not saved to database (future feature)
4. **Limited printer configs**: Currently supports Roland TrueVIS VG3-640

---

## Troubleshooting

### "Module not found" errors
**Solution**: Restart the application. If persists, see TROUBLESHOOTING.md

### "API unavailable" warning
**Solution**:
1. Check `.env` has `ENABLE_API_MODE=true`
2. Verify `ConsumableClient.dll` is in the same folder
3. Try stub mode first: `ENABLE_API_MODE=false`

### Browser shows "Connection refused"
**Solution**:
1. Check console shows "Running on http://127.0.0.1:5000"
2. Try http://localhost:5000 instead
3. Check firewall isn't blocking port 5000

### Order submission times out
**Solution**:
1. This can happen with real blockchain (network delays)
2. Check your internet connection
3. Try again - blockchain may be busy

### "Insufficient inventory" error
**Solution**:
1. This is correct behavior when not enough consumables
2. Reduce quantity or check real inventory balances
3. In stub mode, inventory is empty by design

---

## Providing Feedback

When reporting issues, please include:

1. **Steps to reproduce**: What did you do?
2. **Expected behavior**: What should happen?
3. **Actual behavior**: What actually happened?
4. **Screenshots**: If applicable
5. **Mode**: Stub or Real API?
6. **Console logs**: Copy from the black console window
7. **Browser**: Chrome, Firefox, Edge, etc.
8. **PDF used**: Which test file or your own?

### Feedback Template
```
Issue: [Brief description]

Steps:
1. [First step]
2. [Second step]
3. [What happened]

Expected: [What should happen]
Actual: [What actually happened]

Mode: [Stub / Real API]
Browser: [Chrome 120 / Firefox 121 / etc.]
PDF: [sample_pdfs/business_card.pdf]

Console output:
[Paste relevant logs here]

Screenshot: [Attach if helpful]
```

---

## Files Included

```
PrintOrderWeb/
├── PrintOrderWeb.exe          Main application
├── ConsumableClient.dll       Blockchain API library
├── .env.example               Configuration template
├── README_TESTER.md           This file
├── QUICK_START.txt            3-step quick reference
├── TROUBLESHOOTING.md         Detailed problem solving
├── sample_pdfs/               Test PDF files
│   ├── business_card.pdf
│   └── brochure.pdf
├── templates/                 Web UI templates (bundled)
└── static/                    CSS/JS assets (bundled)
```

---

## Technical Details

### Stack
- **Backend**: Flask (Python 3.11)
- **Blockchain**: ConsumableClient API v2.0.0.1
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **PDF Analysis**: PyPDF library

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
- [ ] Can upload a PDF file
- [ ] Can configure order settings
- [ ] Can submit an order
- [ ] Confirmation page shows results

**Real API Mode**
- [ ] Inventory shows real balances
- [ ] Order submits to blockchain
- [ ] Transaction IDs appear
- [ ] Inventory updates after submission

**User Experience**
- [ ] Forms are intuitive
- [ ] Error messages are helpful
- [ ] Progress indicators work
- [ ] Mobile view is usable

**Edge Cases**
- [ ] Handles insufficient inventory
- [ ] Validates quantity limits
- [ ] Shows errors gracefully
- [ ] Recovers from API failures

---

**Thank you for testing!** 🎉

Your feedback helps make this application better for everyone.
