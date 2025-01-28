# How does i drive upload works?

1) First iDrive takes file input from a browser. This array of objects will vary depending on which of upload method was used:
   - Files upload
   - Folder upload
   - Drag and drop files upload
   - Drag and drop folder upload

2) If it's a drag and drop, it has to scan `dataTransfer` object for files/folders and their relative path.


4) iDrive has to convert all these different data inputs so that they can be 
represented by the same data structure. The structure looks like this:
 
   ``` 
   [  
      {  
         systemFile: {
            lastModified, name, size, type, fullPath*, webkitRelativePath*
         }, 
         fileObj: {
           folderContext, uploadId, path, encryptionMethod, 
           size, type, name, frontendId, createdAt, 
           extension, parentPassword
         }
      }
   ]
   ```

   `*` means the variable may or may not exist depending on if upload method is drag and drop. Either way only path from fileObj should be used.
    This processing is done inside a web worker to not freeze the UI.


5) Once the same data structure is obtained, iDrive can start processing


5) Processed 'files' are added to queue, the queue is sorted; then processUpload is called


6) processUpload calls `prepareRequests` which is an async generator function. It loops over queue and yields requests
   
   **request format:**
    ```
   {
      totalSize: int, type: str, requestId: str, attachments: [
         {
          type, rawBlob, fileObj, fragmentSequence, iv, key
         },
      ]
   }
    ```
   
   rawBlob is either systemFile or a blob depending on whatever it's a file or a thumbnail.
   `prepareRequests` is also responsible for generating thumbnails, and folders if needed.


7) `processUpload` checks concurrentRequests and it can it calls `uploadRequest`. This function generates data structure about files that discord can understand and uploads a single request. `onUploadProgress` callback is used to monitor upload progress and display it in UI.
8) After each request is completed the data about it is appended using `fillAttachmentsInfo` method. if 10 files are fully uploaded it then calls the backend and saves these files into a database.

