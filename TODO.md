| TODO List                                      | Status               |
|------------------------------------------------|----------------------|
| multiple files in 1 Discord attachment support | ⛔  Coming prob never |
| switch to a different backend framework        | ⛔  Coming prob never |
| load balancing with round robin for nginx      | ⛔  Coming prob never |


| BUGS                                                  |
|-------------------------------------------------------|
| Optimize shares                                       |
| zip timeouts on thousands of files                    |
| Virtual list view                                     |

# TODO
1) Move everything into a dedicated service layer
2) Prohibit use of .delete() .save() etc on Models directly (how?)
3) Introduce a new exception ValidationError() into services to make nicer errors
4) Use select for update everywhere
5) add geo ip to nginx itself
6) add auto db backups
7) Fix raw image generating. Ensure files are picked. locked. reclaimed etc