# Source me. Gemini on Vertex AI with application-default credentials.
export GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-TRUE}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
if [ -z "${GOOGLE_CLOUD_PROJECT:-}" ] && [ -f "$HOME/project_id.txt" ]; then
  GOOGLE_CLOUD_PROJECT="$(cat "$HOME/project_id.txt")"; export GOOGLE_CLOUD_PROJECT
fi
export MODEL_NAME="${MODEL_NAME:-gemini-3.8-flash}"
