# How does i drive upload works?

1) First idrive takes file input from a browser. This array of objects will vary depending on:
 - Files upload
 - Folder upload
 - Drag and drop files upload
 - Drag and drop folder upload

2) Show toast about upload start


3) iDrive has to convert all these different data inputs so that they can be 
represented by the same data structure. The structure looks like this:
 
   ``` 
   [ 
      {lastModified, name, size, type, path, 
      systemFile, uploadFolder, encryptionMethod, 
      isEncrypted, uploadId},
      ...

   ]
   ```

4) Once the same data structure is obtained, iDrive can start processing


5) Processed 'files' are added to queue, the queue is sorted; then processUpload is called


6) processUpload checks if there are available requests if not it creates them
 - request format
    ```
   {
      totalSize: int, numberOfFiles: int, type: str, requestId: str, attachments: [
         {
          type, rawChunk, fileObj
         },
      ]
   }
    ```

7) preUploadRequest is called. It unpacks the request, and checks if a file/underlying folder has already been created
if not, it creates them, else grabs from dictionary. parent_id and file_id and appended to the fileObj property


8) uploadRequest is called, it uploads the request with onUploadProgress callbacks.


9) 