| TODO List                                          | Status               |
|----------------------------------------------------|----------------------|
| Optimize shares                                    | Soon                 |
| multiple files in 1 Discord attachment support     | ⛔  Coming prob never |
| switch to a different framework for file streaming | ⛔  Coming prob never |
| load balancing with round robin for nginx          | ⛔  Coming prob never |


| BUGS |
|------|
| ...  |

# TODO
1) Move everything into a dedicated service layer
2) Prohibit use of .delete() .save() etc on Models directly (how?)
3) Introduce a new exception ValidationError() into services to make nicer errors
4) Use select for update everywhere
5) add auto db backups
