import copy
import json
import os
import re
import shutil
import time
import traceback
import uuid
from contextlib import nullcontext
from urllib.request import pathname2url

from .. import util
from .._polyfill import zipfile
from ..util import Info
from .host import Host

REGEX_TARGET_FILENAME_FORMATTER = re.compile(r'%([^%]*)%')


class Importer():
    """Main class for importing.

    For a scrapbook tree:

        item0
            item1
                item1-1
                item1-1
                item1-2
        item1
            item1-1
            item1-1
            item1-2

    Due to a technical limitation, items with same ID won't be inserted to the
    same parent, and thus the reconstructed scrapbook tree will be:

        item0
            item1
                item1-1
                item1-2
        item1
            item1-1
            item1-2
    """
    def __init__(self, book, *,
                 target_id=None,
                 target_index=None,
                 target_filename=None,
                 rebuild_folders=False,
                 prune=False,
                 resolve_id_used='skip',  # skip, replace, new
                 ):
        self.book = book
        self.target_id = target_id or book.ROOT_ITEM_ID
        self.target_index = target_index if (isinstance(target_index, int) and target_index >= 0) else None
        self.target_filename = target_filename or '%ID%'
        self.rebuild_folders = rebuild_folders
        self.prune = prune
        self.resolve_id_used = resolve_id_used

    def run(self, files=None):
        self.book.load_meta_files()
        self.book.load_toc_files()

        self.map_eid_to_info = {}
        self.map_id_to_new_id = {}

        book_meta_orig = copy.deepcopy(self.book.meta)
        book_toc_orig = copy.deepcopy(self.book.toc)

        for file in files:
            if os.path.isdir(file):
                with os.scandir(file) as entries:
                    srcs = sorted(f.path for f in entries if util.is_wsba(f.path))
            elif os.path.isfile(file):
                if not util.is_wsba(file):
                    yield Info('warn', f'Skipped invalid file {os.path.basename(file)!r}')
                    continue
                srcs = [file]
            else:
                yield Info('error', f'Failed to import file {os.path.basename(file)!r}: unable to access file')
                continue

            for src in srcs:
                try:
                    yield Info('debug', f'Importing file {os.path.basename(src)!r}')
                    id, eid, parent_id = yield from self._import_file(src)
                except RuntimeError as exc:
                    # intended raise to skip the import
                    yield Info('error', f'Failed to import file {os.path.basename(src)!r}: {exc}', exc=exc)
                except Exception as exc:
                    # unexpected error
                    traceback.print_exc()
                    yield Info('error', f'Failed to import file {os.path.basename(src)!r}: {exc}', exc=exc)
                else:
                    # finalize a successful import
                    text_parent = '' if parent_id is None else f' (under {parent_id!r})'
                    yield Info('info', f'Imported {id!r}{text_parent}')
                    self.map_eid_to_info.setdefault(eid, {}).setdefault('id', id)
                    if self.prune:
                        yield Info('debug', f'Removing {os.path.basename(src)!r} (prune)')
                        os.remove(src)

        # update files
        if self.book.meta != book_meta_orig:
            yield Info('info', 'Saving changed meta files...')
            self.book.save_meta_files()

        if self.book.toc != book_toc_orig:
            yield Info('info', 'Saving changed TOC files...')
            self.book.save_toc_files()

    def generate_imported_filename(self, id, meta, export_info):
        """Generate an adequate filename (without file extension) for an
        importing item.
        """
        def date_formatter(id, pattern):
            if pattern == '':
                return id

            dt = util.id_to_datetime(id)

            if not dt:
                return ''

            if pattern == 'UTC_DATE':
                return f'{dt.year:04d}-{dt.month:02d}-{dt.day:02d}'

            if pattern == 'UTC_TIME':
                return f'{dt.hour:02d}-{dt.minute:02d}-{dt.second:02d}'

            if pattern == 'UTC_YEAR':
                return f'{dt.year:04d}'

            if pattern == 'UTC_MONTH':
                return f'{dt.month:02d}'

            if pattern == 'UTC_DAY':
                return f'{dt.day:02d}'

            if pattern == 'UTC_HOURS':
                return f'{dt.hour:02d}'

            if pattern == 'UTC_MINUTES':
                return f'{dt.minute:02d}'

            if pattern == 'UTC_SECONDS':
                return f'{dt.second:02d}'

            ldt = dt.astimezone()

            if pattern == 'DATE':
                return f'{ldt.year:04d}-{ldt.month:02d}-{ldt.day:02d}'

            if pattern == 'TIME':
                return f'{ldt.hour:04d}-{ldt.minute:02d}-{ldt.second:02d}'

            if pattern == 'YEAR':
                return f'{ldt.year:04d}'

            if pattern == 'MONTH':
                return f'{ldt.month:02d}'

            if pattern == 'DAY':
                return f'{ldt.day:02d}'

            if pattern == 'HOURS':
                return f'{ldt.hour:02d}'

            if pattern == 'MINUTES':
                return f'{ldt.minute:02d}'

            if pattern == 'SECONDS':
                return f'{ldt.second:02d}'

            return ''

        def formatter(m):
            key = m.group(1)

            if key == '':
                return '%'

            if key == 'ID':
                return id

            if key == 'EID':
                return export_info['id']

            if key == 'UUID':
                return str(uuid.uuid4())

            if key == 'TITLE':
                return meta.get('title', '')

            if key == 'SOURCE':
                return meta.get('source', '')

            key, _, pattern = key.partition(':')

            if key == 'CREATE':
                return str(date_formatter(meta.get('create', ''), pattern))

            if key == 'MODIFY':
                return str(date_formatter(meta.get('modify', ''), pattern))

            if key == 'EXPORT':
                return str(date_formatter(export_info['timestamp'], pattern))

            return ''

        filename = REGEX_TARGET_FILENAME_FORMATTER.sub(formatter, self.target_filename)
        filename = '/'.join(util.validate_filename(s) for s in filename.split('/'))
        return filename

    def _import_file(self, file):
        with zipfile.ZipFile(file) as zh:
            with zh.open('export.json') as fh:
                export_info = json.load(fh)

            if export_info['version'] != 1:
                raise RuntimeError(f'Unsupported archive version: {export_info["version"]!r}')

            with zh.open('meta.json') as fh:
                meta = json.load(fh)

            id = meta.pop('id')
            if id in self.book.SPECIAL_ITEM_ID:
                raise RuntimeError(f'invalid ID {id!r}')

            # skip importing data for a duplicated occurrence of a previously
            # imported item
            imported_id = self.map_eid_to_info.setdefault(export_info['id'], {}).get('id')
            if imported_id is not None:
                id = imported_id
                yield Info('debug', f'Skipped importing data for multi-referenced {id!r}')
            else:
                id = yield from self._import_meta_and_data(id, meta, zh, export_info)

            parent_id = yield from self._insert_to_toc(id, export_info)
            return id, export_info['id'], parent_id

    def _import_meta_and_data(self, id, meta, zh, export_info):
        """Import meta and data

        Returns:
            string: ID of the imported item
        """
        index = meta.get('index', '')

        if index:
            if index.endswith('/index.html'):
                src = f'data/{os.path.dirname(index)}'
            else:
                src = f'data/{index}'

            # determine normal copy dst
            _, ext = os.path.splitext(src)
            filename = self.generate_imported_filename(id, meta, export_info) + ext
            dst = os.path.normpath(os.path.join(self.book.data_dir, filename))
            meta['index'] = filename + ('/index.html' if index.endswith('/index.html') else '')

        # handle resolve cases if id exists
        # may overwrite id, dst, and meta['index']
        if id in self.book.meta:
            if self.resolve_id_used == 'skip':
                raise RuntimeError(f'ID {id!r} already exists')

            elif self.resolve_id_used == 'replace':
                index_old = self.book.meta[id].get('index', '')

                # replace only if index type matches
                if os.path.splitext(index)[1] != os.path.splitext(index_old)[1]:
                    raise RuntimeError('index type not match')

                if index_old.endswith('/index.html') != index.endswith('/index.html'):
                    raise RuntimeError('index type not match')

                yield Info('info', f'Force importing duplicated {id!r}...')

                if index:
                    # use original index
                    meta['index'] = index_old

                    # remove current index file or folder
                    if index.endswith('/index.html'):
                        dst = os.path.normpath(os.path.join(self.book.data_dir, os.path.dirname(index_old)))
                        try:
                            shutil.rmtree(dst)
                        except FileNotFoundError:
                            pass
                    else:
                        dst = os.path.normpath(os.path.join(self.book.data_dir, index_old))
                        try:
                            os.remove(dst)
                        except FileNotFoundError:
                            pass

                self.map_eid_to_info.setdefault(export_info['id'], {}).setdefault('replaced', True)

            elif self.resolve_id_used == 'new':
                new_id = self.book.get_unique_id()
                yield Info('info', f'Importing duplicated {id!r} as {new_id!r}...')
                self.map_id_to_new_id[id] = new_id
                id = new_id

                if index:
                    # overwrite dst and index
                    filename = self.generate_imported_filename(id, meta, export_info) + ext
                    dst = os.path.normpath(os.path.join(self.book.data_dir, filename))
                    meta['index'] = filename + ('/index.html' if index.endswith('/index.html') else '')

            else:
                raise RuntimeError(f'unknown resolve mode: {self.resolve_id_used!r}')

        # import data files
        if index:
            if os.path.lexists(dst):
                raise RuntimeError(f'file {dst!r} already exists')

            yield Info('debug', f'Extracting data files to {self.book.get_subpath(dst)!r}')
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            util.fs.zip_extract(zh, dst, src)

        # import favicon
        for f in zh.namelist():
            if f.startswith('favicon/') and not f.endswith('/'):
                basename = os.path.basename(f)
                iconfile = os.path.join(self.book.tree_dir, 'favicon', basename)
                os.makedirs(os.path.dirname(iconfile), exist_ok=True)

                try:
                    util.fs.zip_extract(zh, iconfile, f)
                except FileExistsError:
                    yield Info('debug', f'Skipped existing favicon cache {basename!r}')
                else:
                    yield Info('info', f'Added favicon cache {basename!r}')

                # rewrite icon property to be consistent with the importing book
                try:
                    base = dst if index.endswith('/index.html') else os.path.dirname(dst)
                except UnboundLocalError:
                    base = self.book.data_dir
                meta['icon'] = pathname2url(os.path.relpath(iconfile, base))

                break

        self.book.meta[id] = meta
        return id

    def _insert_to_toc(self, id, export_info):
        """Insert the importing item to TOC

        Returns:
            string: ID of the parent the item is inserted under
        """
        if self.map_eid_to_info.setdefault(export_info['id'], {}).get('replaced'):
            yield Info('debug', f'Skipped inserting replaced {id!r}')
            return None

        if self.rebuild_folders:
            export_path = export_info['path']
            ref_key = parent_id = export_path[-1]['id']
            parent_id = self.map_id_to_new_id.get(parent_id, parent_id)
        else:
            ref_key = parent_id = self.target_id

        if ref_key in self.map_eid_to_info[export_info['id']].setdefault('refs', set()):
            yield Info('debug', f'Skipped inserting multi-referenced {id!r}')
            return None

        self.map_eid_to_info[export_info['id']]['refs'].add(ref_key)

        if parent_id in self.book.meta or parent_id in self.book.SPECIAL_ITEM_ID:
            self._insert_to_id(id, parent_id)
            return parent_id

        for i in reversed(range(len(export_path) - 1)):
            parent_id = export_path[i]['id']
            if parent_id in self.book.meta or parent_id in self.book.SPECIAL_ITEM_ID:
                break
        else:
            # for a bad path data not starting from 'root'
            i = -1
            parent_id = self.book.ROOT_ITEM_ID

        for j in range(i + 1, len(export_path)):
            new_items = self.book.add_item({
                'title': export_path[j]['title'],
                'type': 'folder',
            }, parent_id)
            new_id = next(iter(new_items))
            yield Info('info', f'Generated folder {new_id!r} under {parent_id!r}')
            self.map_id_to_new_id[export_path[j]['id']] = new_id
            parent_id = new_id

        self._insert_to_id(id, parent_id, allow_insert=False)
        return parent_id

    def _insert_to_id(self, id, parent_id, allow_insert=True):
        parent = self.book.toc.setdefault(parent_id, [])

        if allow_insert and self.target_index is not None:
            parent.insert(self.target_index, id)
            self.target_index += 1
        else:
            parent.append(id)


def run(host, files, book_id='', *, lock=True, **kwargs):
    start = time.time()

    if isinstance(host, Host):
        pass
    elif isinstance(host, str):
        host = Host(host)
    else:
        host = Host(*host)

    # Fail for invalid book ID
    if book_id not in host.books:
        yield Info('error', f'Invalid book {book_id!r}.')
        return

    yield Info('debug', f'Loading book {book_id!r}.')

    try:
        book = host.books[book_id]

        if book.no_tree:
            yield Info('error', f'Unable to import to book {book_id!r} ({book.name!r}) (no_tree).')
            return

        yield Info('info', f'Impoting to book {book_id!r} ({book.name!r}).')
        lh = book.get_tree_lock().acquire() if lock else nullcontext()
        with lh:
            generator = Importer(book, **kwargs)
            yield from generator.run(files)

    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    yield Info('info', '----------------------------------------------------------------------')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
