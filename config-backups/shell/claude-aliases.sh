# Claude Session Management
alias newsession='~/Dev/scripts/new_session.sh'

# Prompt & Navigation
eval "$(starship init zsh)"
eval "$(zoxide init zsh)"

# Lazy-load direnv
_direnv_hook() { eval "$(direnv export zsh 2>/dev/null)" }
precmd_functions+=(_direnv_hook)

--
# Claude Code in new iTerm window
claude-iterm() {
    osascript -e 'tell application "iTerm"
        activate
        set newWindow to (create window with default profile)
        tell current session of newWindow
            write text "cd ~/Dev && claude"
        end tell
    end tell'
}

# Claude model switching
alias claude-model='command cat ~/.claude/settings.json | command grep -A 1 "model"'
alias claude-info='command cat ~/.claude/settings.json'
alias claude-opusplan='echo "Setting to opusplan..." && sed -i.bak "s/\"model\": \".*\"/\"model\": \"opusplan\"/" ~/.claude/settings.json && echo "Done."'
alias claude-sonnet='echo "Setting to sonnet..." && sed -i.bak "s/\"model\": \".*\"/\"model\": \"sonnet\"/" ~/.claude/settings.json && echo "Done."'
alias claude-opus='echo "Setting to opus..." && sed -i.bak "s/\"model\": \".*\"/\"model\": \"opus\"/" ~/.claude/settings.json && echo "Done."'
alias claude-haiku='echo "Setting to haiku..." && sed -i.bak "s/\"model\": \".*\"/\"model\": \"haiku\"/" ~/.claude/settings.json && echo "Done."'

# Cortex Batch
export CORTEX_BATCH_RESEARCH_ENABLED=true
export CORTEX_BATCH_RECOMMENDATIONS_ENABLED=true
--
# Claude Code (API key from Keychain - secure)
alias claude="cd ~/Dev && ~/.local/bin/claude"
export ANTHROPIC_API_KEY=$(security find-generic-password -s "anthropic-api-key" -w 2>/dev/null)

# Cortex Batch Commands
[ -f ~/Dev/scripts/cortex_batch.sh ] && source ~/Dev/scripts/cortex_batch.sh

# === CORTEX BRIEFING (cached, async) ===
if [[ -o interactive ]] && [[ -z "$CORTEX_BRIEFING_SHOWN" ]]; then
    export CORTEX_BRIEFING_SHOWN=1
    {
