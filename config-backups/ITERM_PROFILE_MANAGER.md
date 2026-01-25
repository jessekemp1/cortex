# iTerm Profile Manager

Dynamic iTerm profile management for project-based and task-based terminal workflows.

## Installation

Already installed! Available globally as `iterm-profile`

- **Location**: `/Users/jesse.kemp/Dev/cortex/config-backups/iterm-profile`
- **Symlink**: `/usr/local/bin/iterm-profile`
- **Profiles file**: `~/Library/Application Support/iTerm2/DynamicProfiles/dev-monorepo.json`

## Current Setup

### Permanent Profiles (Ctrl+1-5)

| Shortcut | Profile | Badge | Directory | Purpose |
|----------|---------|-------|-----------|---------|
| Ctrl+1 | Opus | 🤖 OPUS | /Dev | Claude Opus for complex tasks |
| Ctrl+2 | Sonnet | 🤖 SONNET | /Dev | Claude Sonnet (default) |
| Ctrl+3 | Cortex | 🧠 CORTEX | /Dev/cortex | Cortex intelligence work |
| Ctrl+4 | VortexV2 | 🌪️ VORTEX | /Dev/Vortex/VortexV2 | Weather API development |
| Ctrl+5 | AlphaArena | 📊 ARENA | /Dev/alpha_arena | Trading system work |

## Quick Commands

```bash
# List all profiles
iterm-profile list

# Show available color themes
iterm-profile themes

# Create a feature branch profile
iterm-profile create "Feature-XYZ" --emoji 🚀 --color purple --dir ~/Dev/my-project

# Create a bug fix profile
iterm-profile create "Fix-Bug-456" --emoji 🐛 --color red --dir ~/Dev/Vortex/VortexV2

# Create a research profile with Claude Opus
iterm-profile create "Research" --emoji 🔬 --color green --claude-model opus

# Create with custom tags
iterm-profile create "Deploy" --emoji 🚢 --color cyan --tags "ops,deploy"

# Remove a custom profile
iterm-profile remove "Feature-XYZ"

# Remove a permanent profile (use with caution!)
iterm-profile remove "VortexV2" --force
```

## Color Themes

Available colors:
- `orange` - Warm, energetic
- `blue` - Cool, calm (default)
- `purple` - Creative, strategic
- `green` - Growth, success
- `red` - Urgent, critical
- `cyan` - Technical, analytical
- `yellow` - Attention, warning
- `pink` - Experimental, fun
- `teal` - Balanced, professional

## Common Workflows

### Starting a New Feature

```bash
# Create a dedicated profile for your feature
iterm-profile create "Auth-Refactor" --emoji 🔐 --color purple --dir ~/Dev/cortex

# Open new iTerm tab → Select "Auth-Refactor" from profile menu
# Work on your feature in a visually distinct environment
```

### Task-Based Context Switching

```bash
# Morning: Research task
iterm-profile create "Morning-Research" --emoji ☀️ --color yellow --claude-model opus

# Afternoon: Bug fixing
iterm-profile create "Afternoon-Bugs" --emoji 🐛 --color red --dir ~/Dev/Vortex/VortexV2

# Clean up at end of day
iterm-profile remove "Morning-Research"
iterm-profile remove "Afternoon-Bugs"
```

### Client/Project Work

```bash
# Create client-specific profile
iterm-profile create "Client-Acme" --emoji 💼 --color teal --dir ~/Dev/client-acme --tags "client,billable"

# Profile persists across sessions until you remove it
# Clean up when project completes
iterm-profile remove "Client-Acme"
```

## All Profile Features

Every profile (permanent and custom) includes:

✅ Python `file:line` clickable hyperlinks
✅ Red highlighting for FAILED/ERROR/AssertionError
✅ Force-push-to-main blocker alert
✅ Custom badge and window title
✅ Color-coded background
✅ Project-specific working directory

## Advanced Usage

### Custom Commands

```bash
# Docker container profile
iterm-profile create "Docker-Dev" --emoji 🐳 --color cyan --command "docker exec -it mycontainer bash"

# SSH profile
iterm-profile create "Production" --emoji 🚀 --color red --command "ssh user@prod-server"

# Custom script
iterm-profile create "DevEnv" --emoji ⚡ --color yellow --command "/Users/jesse.kemp/scripts/setup-dev.sh"
```

### Updating Permanent Profiles

To modify the 5 permanent profiles, edit the template:
```bash
# Edit template
code /Users/jesse.kemp/Dev/cortex/config-backups/iterm2/dev-monorepo.json

# Restore from template
cd /Users/jesse.kemp/Dev/cortex/config-backups
./cleanup-iterm2-profiles.sh
```

## Tips

- **Dynamic profiles reload automatically** - No need to restart iTerm
- **Use descriptive names** - "Feature-Auth-v2" better than "Test"
- **Color code by priority** - Red for urgent, green for stable, purple for experimental
- **Clean up regularly** - Remove profiles when tasks complete
- **Permanent profiles are protected** - Can't remove without `--force`

## Troubleshooting

### Profile not showing in iTerm
- Profiles auto-reload, but if not visible: Preferences → Profiles → Click reload icon
- Check syntax: `python3 -m json.tool ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json`

### Can't remove profile
- Permanent profiles require `--force` flag
- Check name exactly matches: `iterm-profile list`

### Want to reset to defaults
```bash
cd /Users/jesse.kemp/Dev/cortex/config-backups
./cleanup-iterm2-profiles.sh
```

## File Locations

- **CLI tool**: `/Users/jesse.kemp/Dev/cortex/config-backups/iterm-profile`
- **Active profiles**: `~/Library/Application Support/iTerm2/DynamicProfiles/dev-monorepo.json`
- **Template backup**: `/Users/jesse.kemp/Dev/cortex/config-backups/iterm2/dev-monorepo.json`
- **Preference backups**: `~/Library/Preferences/com.googlecode.iterm2.plist.backup.*`
