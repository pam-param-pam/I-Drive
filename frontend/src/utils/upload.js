import {fetchJSON} from "@/api/utils.js";
import CryptoJS from 'crypto-js';
import store from "@/store";
import {create} from "@/api/folder.js";


export function scanFiles(dt) {
  return new Promise((resolve) => {
    let reading = 0;
    const contents = [];

    if (dt.items !== undefined) {
      for (let item of dt.items) {
        if (
          item.kind === "file" &&
          typeof item.webkitGetAsEntry === "function"
        ) {
          const entry = item.webkitGetAsEntry();
          readEntry(entry);
        }
      }
    } else {
      resolve(dt.files);
    }

    function readEntry(entry, directory = "") {
      if (entry.isFile) {
        reading++;
        entry.file((file) => {
          reading--;

          file.webkitRelativePath = `${directory}${file.name}`;
          contents.push(file);

          if (reading === 0) {
            resolve(contents);
          }
        });
      } else if (entry.isDirectory) {

        readReaderContent(entry.createReader(), `${directory}${entry.name}`);
      }
    }

    function readReaderContent(reader, directory) {
      reading++;

      reader.readEntries(function (entries) {
        reading--;
        if (entries.length > 0) {
          for (const entry of entries) {
            readEntry(entry, `${directory}/`);
          }

          readReaderContent(reader, `${directory}/`);
        }

        if (reading === 0) {
          resolve(contents);
        }
      });
    }
  });
}


function detectExtension(filename) {
  let arry = filename.split(".")

  return "." + arry[arry.length - 1]

}
export async function prepareForUpload(files, parent_folder) {
  let folder_upload =
    files[0].webkitRelativePath !== undefined &&
    files[0].webkitRelativePath !== "";

  let fileList = []

  if (folder_upload) {
    let folder_structure = {}
    for (let file of files) {
      console.log("====file====");
      let folder_list = file.webkitRelativePath.split("/").slice(0, -1);  // Get list of folders by removing the file name
      let folder_list_str = folder_list.join("/");

      console.log(`1:  ${folder_list}`);
      console.log(`2:  ${folder_list_str}`);
      let folder
      for (let i = 1; i <= folder_list.length; i++) {
        // idziemy od tyłu po liscie czyli jesli lista to np [a1, b2, c3, d4, e5, f6]
        // to najpierw bedziemy mieli a1
        // potem a1, b2
        // potem a1, b2, c3
        console.log(`4:  ${folder_list.slice(0, i)}`);
        let folder_list_key = folder_list.slice(0, i).join("/");
        if (!(folder_list_key in folder_structure)) {
          // zapytanie API
          // stwórz folder o nazwie folder_list[0:i][-1] z parent_id = file_structure[folder_list[0:i-1]]
          let parent_list = folder_structure[folder_list.slice(0, i - 1).join("/")]
          let parent_list_id
          let chatgpt_folder_name = folder_list.slice(0, i)[folder_list.slice(0, i).length - 1];

          if (parent_list) {
            parent_list_id = parent_list["id"];
          }
          else {
            parent_list_id = parent_folder.id
            this.$toast.success(`${chatgpt_folder_name} created!`, {
              timeout: 3000,
            });
          }

          console.log("creating " + chatgpt_folder_name)
          folder = await create({"parent_id": parent_list_id, "name": chatgpt_folder_name})
          folder_structure[folder_list_key] = {"id": folder.id, "parent_id": parent_list_id};

        }
      }
      fileList.push({"parent_id": folder.id, "file": file})

    }

    console.log(folder_structure);

  }
  else {
    for (let file of files) {
      fileList.push({"parent_id": parent_folder.id, "file": file})
    }


  }
  await handleFiles(fileList);

}

async function createFiles(fileList, filesInRequest) {
  let createdFiles = []

  let file_res = await fetchJSON(`/api/createfile`, {
    method: "POST",
    body: JSON.stringify({"files": filesInRequest})
  })

  for (let created_file of file_res) {
    let file = fileList[created_file.index].file

    createdFiles.push({"file_id": created_file.file_id, "key": created_file.key, "file": file})
  }
  return createdFiles
}
export async function handleFiles(fileList) {
  console.log("HANDLE FILESSSS")

  fileList.sort((a, b) => a.file.size - b.file.size);
  let createdFiles = []
  let filesInRequest = []

  for (let i = 0; i < fileList.length; i++) {
    let fileObj = fileList[i]
    let file_obj =
      {"name": fileObj.file.name, "parent_id": fileObj.parent_id, "mimetype": fileObj.file.type, "extension": detectExtension(fileObj.file.name), "size": fileObj.file.size, "index": i}

    filesInRequest.push(file_obj)
    if (filesInRequest.length >= 100) {
      createdFiles.push(...await createFiles(fileList, filesInRequest))
      filesInRequest = []
    }
  }
  createdFiles.push(...await createFiles(fileList, filesInRequest))


  const chunkSize = 25 * 1023 * 1024; // <25MB in bytes
  let totalSize = 0
  let fileFormList = new FormData();
  let attachmentJson = []
  let filesForRequest = []
  console.log("UPLOADING FILESSSS1")
  for (let i = 0; i < createdFiles.length; i++) {
    console.log("UPLOADING WOOOOOO" + i.toString())
    let fileObj = createdFiles[i]
    console.log(`1111111111111: ${JSON.stringify(createdFiles)}`)
    console.log(`2222222222222: ${JSON.stringify(createdFiles[i])}`)


    let size = fileObj.file.size
    if (size === 0) continue


    if (size > chunkSize) {
      const chunks = [];
      for (let j = 0; j < size; j += chunkSize) {
        const chunk = fileObj.file.slice(j, j + chunkSize);
        chunks.push(chunk);
      }


      // Upload each chunk
      for (let j = 0; j < chunks.length; j++) {
        await this.uploadChunk(chunks[j], j + 1, chunks.length, fileObj.file_id);
      }
    } else {
        if (totalSize + size > chunkSize  || filesForRequest.length >= 10) {
          await uploadMultiAttachments(fileFormList, attachmentJson, filesForRequest)
          filesForRequest = []
          attachmentJson = []
          fileFormList = new FormData();
          totalSize = 0
        }
        filesForRequest.push(fileObj)
        fileFormList.append(`File ${i + 1}`, fileObj.file, `files[${i}]`);

        attachmentJson.push({
          "id": i+1,
          "description": `File ${i + 1}`,
          "filename": `file${i + 1}`
        })
        totalSize = totalSize + size

    }

  }
  if (attachmentJson.length > 0)   {
    await uploadMultiAttachments(fileFormList, attachmentJson, filesForRequest)
  }
  const item = {
    id: "id",
    path: "path",
    file: "file",
    overwrite: true,
  };
  await store.dispatch("upload/upload", item);


}
export async function uploadMultiAttachments(fileFormList, attachmentJson, filesForRequest) {
  console.log("1: " + fileFormList)
  console.log("2: " + JSON.stringify(attachmentJson))
  console.log("3: " + JSON.stringify(filesForRequest))

  let webhook = store.state.settings.webhook
  console.log("111111111111111111111111")
  console.log(webhook)
  fileFormList.append('json_payload', JSON.stringify({"attachments": attachmentJson}));

  try {
    const response = await fetch(webhook, {
      method: 'POST',
      body: fileFormList
    });

    let json = await response.json();
    if (!response.ok) {
      throw new Error(`Error uploading chunk ${1}/${1}: ${response.statusText}`);
    }
    for (let i = 0; i < json.attachments.length; i++) {
      let attachment = json.attachments[i]
      console.log("aaaaaa: " + JSON.stringify(filesForRequest[i]))
      let fragment_res = await fetchJSON(`/api/createfile`, {
        method: "PATCH",
        body: JSON.stringify(
          {
            "file_id": filesForRequest[i].file_id,
            "fragment_sequence": 1,
            "total_fragments": 1,
            "fragment_size": filesForRequest[i].file.size,
            "message_id": json.id,
            "attachment_id": attachment.id
          }
        )
      })
    }

  } catch (error) {
    console.error(error);
  }
}

export async function uploadChunk(chunk, chunkNumber, totalChunks, file_id) {
  console.log("UPLOAD CHUNK")

  let webhook = store.state.settings.webhook

  const formData = new FormData();
  formData.append('file', chunk, `chunk_${chunkNumber}`);
  try {
    const response = await fetch(webhook, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Error uploading chunk ${chunkNumber}/${totalChunks}: ${response.statusText}`);
    }

    let json = await response.json();

    let fragment_res = await fetchJSON(`/api/createfile`, {
      method: "PATCH",
      body: JSON.stringify(
        {
          "file_id": file_id, "fragment_sequence": chunkNumber, "total_fragments": totalChunks,
          "fragment_size": chunk.size, "message_id": json.id, "attachment_id": json.attachments[0].id
        }
      )
    })

  } catch (error) {
    console.error(error);
  }

}
function encrypt(file, key) {
  var reader = new FileReader();
  reader.onload = () => {
    var wordArray = CryptoJS.lib.WordArray.create(reader.result);           // Convert: ArrayBuffer -> WordArray
    var encrypted = CryptoJS.AES.encrypt(wordArray, key).toString();        // Encryption: I: WordArray -> O: -> Base64 encoded string (OpenSSL-format)

    var fileEnc = new Blob([encrypted]);                                    // Create blob from string

    var a = document.createElement("a");
    var url = window.URL.createObjectURL(fileEnc);
    var filename = file.name + ".enc";
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  };
  reader.readAsArrayBuffer(file);
}

