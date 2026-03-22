import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from novem.exceptions import Novem403, Novem404

from ..api_ref import NovemAPI
from ..shared import NovemShare
from ..tags import NovemTags
from ..utils import cl
from ..utils import colors as clrs
from .config import NovemJobConfig

"""

"""


class NovemJobAPI(NovemAPI):
    config: Optional[NovemJobConfig]
    shared: Optional[NovemShare]
    tags: Optional[NovemTags]
    id: str
    user: Optional[str] = None

    _debug: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if "debug" in kwargs and kwargs["debug"]:
            self._debug = True

        if "user" in kwargs and kwargs["user"]:
            self.user = kwargs["user"]

        if "create" not in kwargs or kwargs["create"]:
            # create when used as an api unless specifically told not to
            self.api_create("")

        self.config = NovemJobConfig(self)
        if self.user:
            base_path = f"users/{self.user}/jobs/{self.id}"
        else:
            base_path = f"jobs/{self.id}"
        self.shared = NovemShare(self, base_path)
        self.tags = NovemTags(self, base_path)

        if "shared" in kwargs:
            self.shared.set(kwargs["shared"])

        if "config" in kwargs:
            self.config.set(kwargs["config"])

        self._parse_kwargs(**kwargs)

    def _parse_kwargs(self, **kwargs: Any) -> None:

        # first let our super do it's thing
        super()._parse_kwargs(**kwargs)

        # get a list of valid properties
        props = [
            x
            for x in dir(self)
            if x[0] != "_" and x not in ["data", "read", "delete", "write", "shared", "config", "create"]
        ]

        for k, v in kwargs.items():

            if k not in props:
                continue

            setattr(self, k, v)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "config" and hasattr(self, "config") and self.config:
            self.config.set(value)
        elif (
            name == "shared"
            and hasattr(self, "shared")
            and self.shared is not None
            and not isinstance(value, NovemShare)
        ):
            self.shared.set(value)
        elif name == "tags" and hasattr(self, "tags") and self.tags is not None and not isinstance(value, NovemTags):
            self.tags.set(value)
        else:
            super().__setattr__(name, value)

    def api_read(self, relpath: str) -> str:
        """
        Read the api value located at realtive path
        """

        qpath = f"{self._api_root}jobs/{self.id}{relpath}"

        if self._debug:
            print(f"GET: {qpath}")

        r = self._session.get(qpath)

        # verify result and raise exception if not ok
        if r.status_code == 404:
            raise Novem404(qpath)

        if r.status_code == 403:
            raise Novem403

        return r.content.decode("utf-8")

    def api_delete(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """

        path = f"{self._api_root}jobs/{self.id}{relpath}"

        if self._debug:
            print(f"DELETE: {path}")

        r = self._session.delete(path)

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(f"DELETE: {path}")
            print("body")
            print("---")
            print(r.text)
            print("headers")
            print("---")
            print(r.headers)
            print("should raise an error")

    def api_create(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """

        path = f"{self._api_root}jobs/{self.id}{relpath}"

        if self._debug:
            print(f"PUT: {path}")

        r = self._session.put(path)

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403(path)

        if r.status_code == 409:
            # we will ignore 409 errors
            # as creating objects that already exist is not a problem
            return

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(f"PUT: {path}")
            print("body")
            print("---")
            print(r.text)
            print("headers")
            print("---")
            print(r.headers)
            print("should raise a general error")

    def api_write(self, relpath: str, value: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """

        path = f"{self._api_root}jobs/{self.id}{relpath}"

        if self._debug:
            print(f"POST: {path}")

        r = self._session.post(
            path,
            headers={"Content-type": "text/plain"},
            data=value.encode("utf-8"),
        )

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(f"POST: {path} {value}")
            print("body")
            print("---")
            print(r.text)
            print(r.status_code)
            print("headers")
            print("---")
            for k, v in r.headers.items():
                print(f"   {k}: {v}")
            print("should raise a general error")

    # chainable utility function for setting values
    def w(self, key: str, value: str) -> Any:
        """
        Set a novem group property, if key is a valid
        class prop then it will set that, else it will
        try to invoke an api call

        (both options results in the same effect)
        """
        props = [x for x in dir(self) if x[0] != "_" and x not in ["data", "read", "delete", "write"]]

        if key in props:
            self.__setattr__(key, value)
        else:
            self.api_write(key, value)

        return self

    def ref(self, ref: str) -> str:
        """
        Return a fully qualified path to given ref

        Grab our userid from whoami
        Grab our id

        So input of "tag:v0.0.2" give "/<user>/<job>:tag:v0.0.2"
        """
        user = self.read("whoami")

        return f"/{user}/{self.id}:{ref}"

    @property
    def log(self) -> None:
        """
        print the current novem logs for the given vis
        """
        print(self.api_read("/log"))

        return None

    # job options
    @property
    def type(self) -> str:
        return self.api_read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self.api_write("/config/type", value)

    @property
    def name(self) -> str:
        return self.api_read("/name").strip()

    @name.setter
    def name(self, value: str) -> None:
        return self.api_write("/name", value)

    @property
    def description(self) -> str:
        return self.api_read("/description")

    @description.setter
    def description(self, value: str) -> None:
        return self.api_write("/description", value)

    @property
    def summary(self) -> str:
        return self.api_read("/summary")

    @summary.setter
    def summary(self, value: str) -> None:
        return self.api_write("/summary", value)

    @property
    def url(self) -> str:
        return self.api_read("/url").strip()

    @property
    def shortname(self) -> str:
        return self.api_read("/shortname").strip()

    @staticmethod
    def _parse_filename(content_disposition: str) -> Optional[str]:
        """Extract filename from Content-Disposition header."""
        # Try RFC 8187 filename* first (UTF-8 encoded)
        m = re.search(r"filename\*\s*=\s*UTF-8''(.+?)(?:;|$)", content_disposition, re.IGNORECASE)
        if m:
            from urllib.parse import unquote

            return unquote(m.group(1).strip())
        # Fall back to plain filename
        m = re.search(r'filename\s*=\s*"?([^";]+)"?', content_disposition)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _dedup_path(folder: str, name: str) -> str:
        """Return a path in *folder* for *name*, adding (1), (2), … on conflict."""
        candidate = os.path.join(folder, name)
        if not os.path.exists(candidate):
            return candidate
        base, ext = os.path.splitext(name)
        n = 1
        while True:
            candidate = os.path.join(folder, f"{base} ({n}){ext}")
            if not os.path.exists(candidate):
                return candidate
            n += 1

    def run(self, files: Optional[List[str]] = None, output: Optional[str] = None) -> None:
        """
        Trigger a job run by posting to /data.

        If *files* is provided, each entry must be prefixed with ``@``
        (e.g. ``@data.csv``).  The files are sent as ``multipart/form-data``
        with field names ``file_0``, ``file_1``, … and the original filename
        preserved.  Without files, an empty JSON body is sent.

        If *output* is provided, the response body is saved to that directory
        (created if necessary) using the filename from the server's
        Content-Disposition header.
        """
        path = f"{self._api_root}jobs/{self.id}/data"

        if self._debug:
            print(f"POST: {path}")

        if files:
            multipart: List[Tuple[str, Any]] = []
            for idx, raw in enumerate(files):
                if not raw.startswith("@"):
                    print(f"Error: file arguments must start with @, got: {raw}")
                    sys.exit(1)
                fpath = raw[1:]
                if not os.path.isfile(fpath):
                    print(f"Error: file not found: {fpath}")
                    sys.exit(1)
                multipart.append((f"file_{idx}", (os.path.basename(fpath), open(fpath, "rb"))))
            if self._debug:
                names = [os.path.basename(raw[1:]) for raw in files]
                print(f"  files: {names}")
            r = self._session.post(path, files=multipart, stream=bool(output))
        else:
            r = self._session.post(
                path,
                headers={"Content-type": "application/json; charset=utf-8"},
                data="{}",
                stream=bool(output),
            )

        if not r.ok:
            # Try to parse error message from JSON response
            try:
                error_data = r.json()
                if "error" in error_data:
                    print(f"Error: {error_data['error']}")
                else:
                    print(f"Error: {r.text}")
            except Exception:
                print(f"Error: {r.text}")
            sys.exit(1)

        if output:
            os.makedirs(output, exist_ok=True)
            cd = r.headers.get("Content-Disposition", "")
            name = self._parse_filename(cd) or "output"
            dest = self._dedup_path(output, name)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(dest)
        elif r.content:
            print(r.text)

    def api_dump(self, outpath: str) -> None:
        """
        Iterate over current job and dump output to supplied path
        """

        # Base path without trailing slash
        qpath = f"{self._api_root}jobs/{self.id}"

        # create util function
        def rec_tree(path: str) -> None:
            qp = f"{qpath}{path}"
            fp = f"{outpath}{path}"
            req = self._session.get(qp)

            if not req.ok:
                return None

            headers = req.headers
            tp = headers.get("X-NVM-Type", headers.get("X-NS-Type", "file"))

            # if i am a file, write to disc
            if tp == "file":
                # skip files with default values
                if headers.get("x-nvm-default", "").lower() == "true":
                    print(f"Skipping default: {fp}")
                    return None
                # ensure parent directory exists before writing
                parent_dir = os.path.dirname(fp)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                    print(f"Creating folder: {parent_dir}")
                with open(fp, "w") as f:
                    f.write(req.text)
                print(f"Writing file:    {fp}")
                return None

            # if I am a folder, recurse without creating yet
            nodes: List[Dict[str, str]] = req.json()

            # Recurse relevant structure (skip system entries and read-only files)
            for r in nodes:
                if r["type"] in ["system_file", "system_dir"]:
                    continue
                child_path = f'{path}/{r["name"]}'
                child_fp = f"{outpath}{child_path}"

                # /shared/ and /tags/ are special markers - create empty files from listing
                if r["type"] in ["file", "link"] and (
                    child_path.startswith("/shared/") or child_path.startswith("/tags/")
                ):
                    parent_dir = os.path.dirname(child_fp)
                    if parent_dir and not os.path.exists(parent_dir):
                        os.makedirs(parent_dir, exist_ok=True)
                        print(f"Creating folder: {parent_dir}")
                    with open(child_fp, "w") as f:
                        f.write("")
                    print(f"Writing file:    {child_fp}")
                    continue

                # skip read-only files/links
                if r["type"] in ["file", "link"] and "w" not in r.get("permissions", []):
                    continue
                rec_tree(child_path)

        # start recursion
        rec_tree("/")

    def api_load(self, inpath: str) -> None:
        """
        Load a dumped folder structure back into the API.
        Walks the folder and for each file: PUT to create, then POST content.
        """

        qpath = f"{self._api_root}jobs/{self.id}"

        def load_tree(local_path: str, api_path: str) -> None:
            full_local = os.path.join(inpath, local_path.lstrip("/")) if local_path else inpath

            if os.path.isfile(full_local):
                # Read file content
                with open(full_local, "r") as f:
                    content = f.read()

                full_api = f"{qpath}{api_path}"

                # Try PUT first to create the resource
                r = self._session.put(full_api)
                put_status = r.status_code

                # POST the content
                r = self._session.post(
                    full_api,
                    headers={"Content-type": "text/plain"},
                    data=content.encode("utf-8"),
                )
                print(f"Loaded file:     {api_path} (PUT: {put_status}, POST: {r.status_code}, {len(content)} bytes)")

            elif os.path.isdir(full_local):
                print(f"Processing dir:  {api_path or '/'}")

                # Iterate over directory contents
                for entry in sorted(os.listdir(full_local)):
                    entry_local = os.path.join(local_path, entry) if local_path else entry
                    entry_api = f"{api_path}/{entry}"
                    load_tree(entry_local, entry_api)

        # Start loading from root
        load_tree("", "")

    def api_tree(self, colors: bool = False, relpath: str = "/") -> str:
        """
        Iterate over the current job and print a "pretty" ascii tree
        """
        if relpath[0] != "/":
            relpath = f"/{relpath}"

        clrs()

        # Base path without trailing slash - we'll add paths in rec_tree
        qpath = f"{self._api_root}jobs/{self.id}"

        # some display options
        c = "├"
        b = "└"
        v = "│"
        h = "─"

        # create util function
        def rec_tree(path: str, level: int = 0, last: List[bool] = [False]) -> Tuple[List[str], str]:
            qp = f"{qpath}{path}"
            req = self._session.get(qp)

            if not req.ok:
                if level == 0:
                    # Top level failure - show error to user
                    if req.status_code == 404:
                        print(f"Job '{self.id}' not found")
                    else:
                        print(f"Failed to fetch job tree: {req.status_code}")
                    sys.exit(1)
                return ([], "")

            headers = req.headers
            tp = headers.get("X-NVM-Type", headers.get("X-NS-Type", "file"))

            if tp == "file":
                print("The tree display is only available for `dir` paths")
                sys.exit(-1)

            nodes: List[Dict[str, str]] = req.json()

            hdp: List[str] = []
            if level == 0:
                hdp = headers.get("X-NVM-Permissions", headers.get("X-NS-Permissions", "")).split(", ")

            pfx = ""
            for il in last:
                if il:
                    pfx += "    "
                else:
                    pfx += f"{v}   "

            # drop system stuff
            nodes = [x for x in nodes if x["type"] not in ["system_file", "system_dir"]]

            resp = ""
            # convert element into a tree structure
            nodes = sorted(nodes, key=lambda k: (k["type"], k["name"]))
            for r in nodes:
                rd = "r" if "r" in r["permissions"] else "-"
                w = "w" if "w" in r["permissions"] else "-"
                d = "d" if "d" in r["permissions"] else "-"
                if colors:
                    a = f"{cl.FGGRAY}[{rd}{w}{d}]{cl.ENDC}"
                else:
                    a = f"[{rd}{w}{d}]"

                if r["name"] == nodes[-1]["name"]:
                    mc = last + [True]
                    co = f"{b}"
                else:
                    mc = last + [False]
                    co = f"{c}"

                if r["type"] == "dir":
                    if colors:
                        resp += f"{pfx}{co}{h}{h} {a} {cl.OKBLUE}" f'{r["name"]}/{cl.ENDC}\n'
                    else:
                        resp += f'{pfx}{co}{h}{h} {a} {r["name"]}/\n'

                    resp += rec_tree(f'{path}/{r["name"]}', level + 1, mc)[1]
                else:
                    resp += f'{pfx}{co}{h}{h} {a} {r["name"]}\n'

            # order by dir, files, alphabetically
            return (hdp, resp)

        hdp, tr = rec_tree(relpath, 0, [True])

        sf = f"{self.id}{relpath}"
        if sf[-1] != "/":
            sf = f"{sf}/"

        if colors:
            sf = f"{cl.OKBLUE}{sf}{cl.ENDC}"

        rd = "r" if "r" in hdp else "-"
        w = "w" if "w" in hdp else "-"
        d = "d" if "d" in hdp else "-"
        if colors:
            a = f"{cl.FGGRAY}[{rd}{w}{d}]{cl.ENDC}"
        else:
            a = f"[{rd}{w}{d}]"
        tr = f"{a} {sf}\n{tr}"

        return tr[:-1]  # strip trailing newline


class Job(NovemJobAPI):
    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id = id
        super().__init__(**kwargs)
