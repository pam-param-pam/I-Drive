from typing import TypeAlias, Union

from website.models import Folder, File

Resource: TypeAlias = Union[Folder, File]
