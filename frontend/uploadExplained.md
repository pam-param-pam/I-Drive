# How does i drive upload works?

1) First idrive takes file input from a browser. This array of objects will vary on:
 - Files upload
 - Folder upload
 - Drag and drop files upload
 - Drag and drop folder upload
1) iDrive has to convert all these different data inputs so that they can be 
represented by the same data structure. The structure looks like this:
 
   ``` 
   [ 
      {lastModified, name, size, type, path, 
      systemFile, uploadFolder, encryptionMethod, 
      isEncrypted, frontendId, uploadId},
      ...

   ]
   ```

2) Once the same data structure is obtained, iDrive can start processing

