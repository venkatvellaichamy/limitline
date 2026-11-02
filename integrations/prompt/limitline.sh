# Source from ~/.bashrc or ~/.zshrc.
# The prompt function never calls the network.
limitline_prompt() {
  limitline --host prompt 2>/dev/null
}

# bash
# PS1='$(limitline_prompt) '"$PS1"

# zsh
# setopt PROMPT_SUBST
# PS1='$(limitline_prompt) '"$PS1"
