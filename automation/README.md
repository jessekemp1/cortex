# Cortex Daily Automation

This directory contains automation configuration for running Cortex scans automatically.

## LaunchAgent Setup (macOS)

The LaunchAgent runs `daily_scan.sh` every day at 8:00 AM.

### Installation

1. **Copy the plist file to LaunchAgents directory:**
   ```bash
   cp com.cortex.daily.plist ~/Library/LaunchAgents/
   ```

2. **Load the agent:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.cortex.daily.plist
   ```

3. **Verify it's loaded:**
   ```bash
   launchctl list | grep cortex
   ```

### Testing

To test the automation without waiting for 8am:

```bash
launchctl start com.cortex.daily
```

Check the logs:
```bash
tail -f ~/.cortex/logs/daily_scan.log
```

### Monitoring

Logs are written to:
- **Standard output**: `~/.cortex/logs/daily_scan.log`
- **Errors**: `~/.cortex/logs/daily_scan_error.log`

Check logs regularly to ensure scans are running successfully:

```bash
# View recent scans
tail -50 ~/.cortex/logs/daily_scan.log

# Check for errors
cat ~/.cortex/logs/daily_scan_error.log
```

### Disable Automation

To stop automatic daily scans:

```bash
launchctl unload ~/Library/LaunchAgents/com.cortex.daily.plist
```

You can still run manual scans anytime:
```bash
cd $CORTEX_DIR
./daily_scan.sh
```

### Re-enable Automation

```bash
launchctl load ~/Library/LaunchAgents/com.cortex.daily.plist
```

## Configuration

The LaunchAgent is configured to:
- Run every day at 8:00 AM
- Use `$CORTEX_DIR` as working directory
- Log output to `~/.cortex/logs/daily_scan.log`
- Log errors to `~/.cortex/logs/daily_scan_error.log`
- Use standard PATH including Homebrew

## Customization

### Change Schedule Time

Edit `com.cortex.daily.plist` and modify the `StartCalendarInterval`:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>9</integer>  <!-- Change to 9 for 9am -->
    <key>Minute</key>
    <integer>30</integer>  <!-- Change to 30 for :30 past -->
</dict>
```

After editing, reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.cortex.daily.plist
cp com.cortex.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.cortex.daily.plist
```

### Run Multiple Times Per Day

To run twice daily (8am and 2pm), create additional calendar intervals:

```xml
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <dict>
        <key>Hour</key>
        <integer>14</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</array>
```

### Weekdays Only

To skip weekends, add:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
    <key>Weekday</key>
    <integer>1-5</integer>  <!-- Monday through Friday -->
</dict>
```

## Linux/Cron Alternative

For Linux systems, use cron instead:

```bash
# Edit crontab
crontab -e

# Add this line for 8am daily:
0 8 * * * $CORTEX_DIR/daily_scan.sh >> ~/.cortex/logs/daily_scan.log 2>> ~/.cortex/logs/daily_scan_error.log
```

## Troubleshooting

### Agent Not Running

Check if it's loaded:
```bash
launchctl list | grep cortex
```

If not listed, load it:
```bash
launchctl load ~/Library/LaunchAgents/com.cortex.daily.plist
```

### Permission Errors

Ensure the scripts are executable:
```bash
chmod +x $CORTEX_DIR/daily_scan.sh
chmod +x $CORTEX_DIR/cortex_mvp
```

### Path Issues

If commands aren't found, verify the PATH in the plist includes:
- `/opt/homebrew/bin` (Homebrew M1/M2 Macs)
- `/usr/local/bin` (Homebrew Intel Macs)
- Python installation directory

### Python/Venv Issues

Ensure the venv exists and is working:
```bash
cd $CORTEX_DIR
source venv/bin/activate
python --version
pip list
```

## Best Practices

1. **Monitor logs weekly** - Check for errors or issues
2. **Keep scripts updated** - Pull latest changes regularly
3. **Test after system updates** - macOS updates may disable LaunchAgents
4. **Backup automation config** - Keep the plist in version control
5. **Review scan results** - Don't just automate and ignore

## Integration with Notifications

To get notified when scans complete, you can add a notification to the scan script:

```bash
# At the end of daily_scan.sh
osascript -e 'display notification "Cortex daily scan complete" with title "Cortex"'
```

Or use more advanced notification tools like `terminal-notifier`:

```bash
brew install terminal-notifier
terminal-notifier -title "Cortex" -message "Daily scan complete" -open "http://localhost:8501"
```

## Security Considerations

- The LaunchAgent runs with your user permissions
- Logs may contain sensitive information - keep them secure
- API keys and credentials should be in `.env`, not scripts
- Review generated contracts before auto-execution
- Consider limiting auto-execution to non-production changes

## Support

For issues with:
- **LaunchAgent setup**: Check macOS Console app for system logs
- **Script execution**: Check `~/.cortex/logs/daily_scan_error.log`
- **Cortex functionality**: Run `./cortex_mvp health` for diagnostics
