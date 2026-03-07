#!/bin/bash
# Example post-tool-use hook
echo "Sanitizing tool output before returning to model..."
jq 'if .error then error(.error) else . end' "$1"
