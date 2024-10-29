# How does i drive upload works?

1) First iDrive takes file input from a browser. This array of objects will vary depending on:
 - Files upload
 - Folder upload
 - Drag and drop files upload
 - Drag and drop folder upload

2) Show toast about upload start

2) If its a drag and drop, it scans the `dataTransfer` object for all files.


3) iDrive has to convert all these different data inputs so that they can be 
represented by the same data structure. The structure looks like this:
 
   ``` 
   [  
      {  
         systemFile: {
            lastModified, name, size, type, fullPath*, webkitRelativePath*
         }, 
         fileObj: {
            path, uploadFolder, encryptionMethod, 
            isEncrypted, uploadId, folderContext, 
            size, name, type
         }
      }
   ]
   ```

   `*` means the variable may or may not exist depending on some factors, either way, only path from fileObj should be used.


5) Once the same data structure is obtained, iDrive can start processing


5) Processed 'files' are added to queue, the queue is sorted; then processUpload is called


6) processUpload calls `prepareRequests` which is a generator function. It loops over queue and yields requests
 - request format
    ```
   {
      totalSize: int, type: str, requestId: str, attachments: [
         {
          type, rawFileData, fileObj, fragmentSequence
         },
      ]
   }
    ```
   
   rawFileData is either systemFile or a blob depending on whatever its a file or a thumbnail

7) preUploadRequest is called. It unpacks the request, and checks if a file/underlying folders has already been created
if not, it creates them, else grabs from dictionary. parentId and fileId are appended to the fileObj property.


8) uploadRequest is called, it uploads the request with onUploadProgress callbacks.


9) 