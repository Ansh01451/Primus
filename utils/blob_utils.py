from io import BytesIO
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError, AzureError
from fastapi import HTTPException, status

from config import settings
from .log import logger

blob_service_client = BlobServiceClient.from_connection_string(settings.blob_connection_string)
CONTAINER_NAME = settings.container_name

def upload_blob_from_file(file_name: str, file_content: BytesIO):
    try:
        # Get the blob client to upload
        container_name = CONTAINER_NAME
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)
        
        # Attempt to upload the blob
        blob_client.upload_blob(file_content, overwrite=True)
        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{file_name}"
        print(f"Successfully uploaded: {file_name}")
        return blob_url
    
    except ResourceNotFoundError as e:
        # Raised if the specified container does not exist
        logger(str(e), "upload_blob_from_file", {"file_name": file_name}, status_code=404)
        raise HTTPException(status_code=404, detail=f"Container '{container_name}' not found. Error: '{str(e)}'")
    
    except AzureError as storage_error:
        # Handle storage-specific errors
        logger(str(storage_error), "upload_blob_from_file", {"file_name": file_name}, status_code=400)
        raise HTTPException(status_code=400, detail=f"Blob storage error while uploading '{file_name}': {str(storage_error)}")
    
    except Exception as e:
        # Catch any unexpected errors
        logger(str(e), "upload_blob_from_file", {"file_name": file_name}, status_code=500)
        raise HTTPException(status_code=500, detail=f"Unexpected error while uploading '{file_name}': {str(e)}")

