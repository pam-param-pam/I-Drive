| TODO List                                              | Status               |
|--------------------------------------------------------|----------------------|
| Optimize shares                                        | ❌  Coming one day    |
| cached docker build                                    | ❌  Coming one day    |
| Virtual list view                                      | ⛔  Coming prob never |
| Stop, pause, abort uploads                             | ⛔  Coming prob never |
| Editor support for large files                         | ⛔  Coming prob never |
| Change  __prependStaticUrl                             | ⛔  Coming prob never |
| multiple files in 1 Discord attachment support         | ⛔  Coming prob never |
| add deselect                                           | ⛔  Coming prob never |
| add multiple file select for mobile                    | ⛔  Coming prob never |
| switch to a different backend framework                | ⛔  Coming prob never |
| load balancing with round robin for nginx              | ⛔  Coming prob never |
| add resolution to images                               | ⛔  Coming prob never |

fix urls mapping, clean Discord class, tasks, shares

| BUGS                                                                    |
|-------------------------------------------------------------------------|
| fix 401 in locked folders in shares                                     |
| Fix file download for mobile                                            |
| fix tasks                                                               |
| fix mobile number download info frontend                                |
| CannotProcessDiscordRequestError in tasks                               |
| remove dangling discord attachments is buggy at best                    |
| zip timeouts on thousands of files                                      |
| share -> settings error                                                 |
| upload file prompt displays on top of context menu                      |
| handle empty files (upload, editor, anything else)                      |
| fix next/prev on desktop with images move                               |
| share password bugged                                                   |
| 0 byte (corrupted uploaded file) causes zip download to completely fail |
| fix locked folders duplicate tab                                        |
| fix upload on frontend and make it less error prone                     |
| fix race conditions in upload on frontend                               |
| fix  discord failed requests in upload process                          |