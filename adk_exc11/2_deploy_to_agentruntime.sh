# Check if .env file exists
if [ -f agent/.env ]; then
  # Export variables from .env file
  export $(grep -v '^#' agent/.env | xargs)
fi


export APP_NAME="adkagent-on-agentruntime"

adk deploy agent_engine \
--project=${GOOGLE_CLOUD_PROJECT} \
--region=${GOOGLE_CLOUD_AGENTRUNTIME_HOSTING_LOCATION} \
--display_name="Agent deployed to Agent Engine" \
agent