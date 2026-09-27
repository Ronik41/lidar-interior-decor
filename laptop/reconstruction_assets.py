"""Read-only, explicit reconstruction inventory bound to the matching raw scan."""
import hashlib
import json
from pathlib import Path, PurePosixPath

class ReconstructionAssets:
    def __init__(self,folder,store):
        self.root=Path(folder).resolve()
        self.metadata=json.loads((self.root/'reconstruction.json').read_text())
        if self.metadata.get('source_scan_id')!=store.source['scan_id']:
            raise ValueError('Reconstruction belongs to a different RoomPlan session; explicit registration is required')
        index=store.scan/'Frames.json'
        if not index.exists() or hashlib.sha256(index.read_bytes()).hexdigest()!=self.metadata.get('frames_sha256'):
            raise ValueError('Reconstruction frame provenance does not match this scan')
        self.files={}
        for name,digest in self.metadata['assets'].items():
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or str(path)!=name: raise ValueError('Unsafe reconstruction asset path')
            disk=self.root/name
            if disk.is_symlink() or not disk.is_file() or not disk.resolve().is_relative_to(self.root): raise ValueError('Missing or unsafe reconstruction asset')
            if hashlib.sha256(disk.read_bytes()).hexdigest()!=digest: raise ValueError('Reconstruction checksum mismatch: '+name)
            self.files[name]=disk
        for key in ('mesh_url','splat_url'):
            if self.metadata.get(key) and self.metadata[key].removeprefix('/reconstruction/') not in self.files: raise ValueError('Unlisted reconstruction model')

    def payload(self):
        return {k:v for k,v in self.metadata.items() if k!='assets'}
