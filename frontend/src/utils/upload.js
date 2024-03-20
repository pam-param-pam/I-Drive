import {fetchJSON} from "@/api/utils.js";
import CryptoJS from 'crypto-js';


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

          file.fullPath = `${directory}${file.name}`;
          contents.push(file);

          if (reading === 0) {
            resolve(contents);
          }
        });
      } else if (entry.isDirectory) {
        const dir = {
          isDir: true,
          size: 0,
          fullPath: `${directory}${entry.name}`,
          name: entry.name,
        };

        contents.push(dir);

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

function detectType(mimetype) {
  if (mimetype.startsWith("video")) return "video";
  if (mimetype.startsWith("audio")) return "audio";
  if (mimetype.startsWith("image")) return "image";
  if (mimetype.startsWith("pdf")) return "pdf";
  if (mimetype.startsWith("text")) return "text";
  return "unknown";
}
function detectExtension(filename) {
  let arry = filename.split(".")

  return "." + arry[arry.length - 1]

}

export async function handleFiles(files, folder) {
  for (let i = 0; i < files.length; i++) {
    let file = files[i];

    let file_res = await fetchJSON(`/api/createfile`, {
      method: "POST",
      body: JSON.stringify(
        {"name": file.name, "parent_id": folder.id, "type": detectType(file.type), "extension": detectExtension(file.name), "size": file.size}
      )
    })
    let id = file_res.file_id
    let key = file_res.key
    let webhook = file_res.webhook_url


    const chunkSize = 25 * 1023 * 1024; // <25MB in bytes

    const chunks = [];
    for (let i = 0; i < file.size; i += chunkSize) {
      const chunk = file.slice(i, i + chunkSize);
      chunks.push(chunk);
    }

    // Upload each chunk
    for (let i = 0; i < chunks.length; i++) {
      await this.uploadChunk(chunks[i], i + 1, chunks.length, webhook, id);
    }
    //encrypt(file, key)
  }
}

export async function uploadChunk(chunk, chunkNumber, totalChunks, webhook, id) {
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


    console.log(response)
    let json = await response.json();
    console.log(json)
    console.log(json.id)

    let fragment_res = await fetchJSON(`/api/createfile`, {
      method: "PATCH",
      body: JSON.stringify(
        {"file_id": id, "fragment_sequence": chunkNumber, "total_fragments": totalChunks, "fragment_size": chunk.size, "message_id": json.id}
      )
    })
    console.log(`Chunk ${chunkNumber}/${totalChunks} uploaded successfully.`);
    console.log(fragment_res)

  } catch (error) {
    console.error(error);
  }
}
export async function uploadFragment(files, folder) {


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
