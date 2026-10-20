# Check if .env file exists
if [ -f agent/.env ]; then
  # Export variables from .env file
  export $(grep -v '^#' agent/.env | xargs)
fi


export APP_NAME="adkagent-on-cloudrun"

adk deploy cloud_run \
--project=${GOOGLE_CLOUD_PROJECT} \
--region=${GOOGLE_CLOUD_HOSTING_LOCATION} \
--service_name=${APP_NAME} \
--with_ui \
--adk_version="2.12.0" \
--env GOOGLE_GENAI_USE_VERTEXAI=TRUE --env GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION} \
agent