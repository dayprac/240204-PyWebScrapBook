from unittest import mock
import unittest
import os
import shutil
import zipfile
import time
import re
import glob
from base64 import b64decode
from email.utils import format_datetime

from webscrapbook import WSB_DIR
from webscrapbook import util
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook.convert import items as conv_items

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_convert')

def setUpModule():
    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', test_root),
        ]
    for mocking in mockings:
        mocking.start()

def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

class TestRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_input = os.path.join(test_root, 'input')
        cls.test_input_config = os.path.join(cls.test_input, WSB_DIR, 'config.ini')
        cls.test_input_tree = os.path.join(cls.test_input, WSB_DIR, 'tree')
        cls.test_input_meta = os.path.join(cls.test_input_tree, 'meta.js')
        cls.test_input_toc = os.path.join(cls.test_input_tree, 'toc.js')
        cls.test_output = os.path.join(test_root, 'output')
        cls.test_output_tree = os.path.join(cls.test_output, WSB_DIR, 'tree')
        cls.test_output_meta = os.path.join(cls.test_output_tree, 'meta.js')
        cls.test_output_toc = os.path.join(cls.test_output_tree, 'toc.js')

    def setUp(self):
        """Set up a general temp test folder
        """
        os.makedirs(self.test_input_tree, exist_ok=True)
        os.makedirs(self.test_output, exist_ok=True)

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_input)
        except NotADirectoryError:
            os.remove(self.test_input)
        except FileNotFoundError:
            pass

        try:
            shutil.rmtree(self.test_output)
        except NotADirectoryError:
            os.remove(self.test_output)
        except FileNotFoundError:
            pass

    def test_param_type(self):
        """Check type filter
        """
        types = ['', 'site', 'image', 'file', 'combine', 'note', 'postit', 'bookmark', 'folder', 'separator']
        for type in types:
            with self.subTest(type=type):
                self.setUp()
                try:
                    with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
                        fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "%s",
    "index": "20200101000000000/index.html"
  }
})""" % type)

                    index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
                    os.makedirs(os.path.dirname(index_file), exist_ok=True)
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write("""dummy""")

                    for info in conv_items.run(self.test_input, self.test_output, format='htz', types=[type]):
                        pass

                    self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
                        os.path.join(self.test_output, ''),
                        os.path.join(self.test_output, '20200101000000000.htz'),
                        })
                finally:
                    self.tearDown()

                self.setUp()
                try:
                    with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
                        fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "%s",
    "index": "20200101000000000/index.html"
  }
})""" % type)

                    index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
                    os.makedirs(os.path.dirname(index_file), exist_ok=True)
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write("""dummy""")

                    for info in conv_items.run(self.test_input, self.test_output, format='htz', types=[]):
                        pass

                    self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
                        os.path.join(self.test_output, ''),
                        os.path.join(self.test_output, '20200101000000000'),
                        os.path.join(self.test_output, '20200101000000000', 'index.html'),
                        })
                finally:
                    self.tearDown()

    def test_param_format_folder01(self):
        """Test format "folder"

        - Folder converted from MAFF should not contain index.rdf
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "index": "20200101000000001/index.html"
  },
  "20200101000000002": {
    "type": "",
    "index": "20200101000000002.htz"
  },
  "20200101000000003": {
    "type": "",
    "index": "20200101000000003.maff"
  },
  "20200101000000004": {
    "type": "",
    "index": "20200101000000004.html"
  },
  "20200101000000005": {
    "type": "",
    "index": "20200101000000005.txt"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000001')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'resource.txt'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")
            zh.writestr('resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000003/index.html', """my page content""")
            zh.writestr('20200101000000003/index.rdf', """dummy""")
            zh.writestr('20200101000000003/resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        index_file = os.path.join(self.test_input, '20200101000000005.txt')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        for info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
            os.path.join(self.test_output, '20200101000000001', 'resource.txt'),
            os.path.join(self.test_output, '20200101000000002'),
            os.path.join(self.test_output, '20200101000000002', 'index.html'),
            os.path.join(self.test_output, '20200101000000002', 'resource.txt'),
            os.path.join(self.test_output, '20200101000000003'),
            os.path.join(self.test_output, '20200101000000003', 'index.html'),
            os.path.join(self.test_output, '20200101000000003', 'resource.txt'),
            os.path.join(self.test_output, '20200101000000004.html'),
            os.path.join(self.test_output, '20200101000000005.txt'),
            })

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001', 'index.html')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000002.htz')) as zh:
            self.assertEqual(
                util.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002', 'index.html')).st_mtime,
                )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000003', 'index.html')).st_mtime,
                )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002/index.html',
                },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003/index.html',
                },
            '20200101000000004': {
                'type': '',
                'index': '20200101000000004.html',
                },
            '20200101000000005': {
                'type': '',
                'index': '20200101000000005.txt',
                },
            })

    def test_param_format_folder02(self):
        """Check if icon path is correctly handled for htz => folder.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.htz",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
            })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': '../.wsb/tree/favicon/favicon.ico',
                },
            })

    def test_param_format_folder03(self):
        """Check if icon path is correctly handled for maff => folder.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.maff",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """my page content""")
            zh.writestr('20200101000000000/index.rdf', """dummy""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
            })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': '../.wsb/tree/favicon/favicon.ico',
                },
            })

    def test_param_format_htz01(self):
        """Test format "htz"

        - HTZ converted from MAFF should not contain index.rdf
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "index": "20200101000000001/index.html"
  },
  "20200101000000002": {
    "type": "",
    "index": "20200101000000002.htz"
  },
  "20200101000000003": {
    "type": "",
    "index": "20200101000000003.maff"
  },
  "20200101000000004": {
    "type": "",
    "index": "20200101000000004.html"
  },
  "20200101000000005": {
    "type": "",
    "index": "20200101000000005.txt"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000001')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'resource.txt'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")
            zh.writestr('resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000003/index.html', """my page content""")
            zh.writestr('20200101000000003/index.rdf', """dummy""")
            zh.writestr('20200101000000003/resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        index_file = os.path.join(self.test_input, '20200101000000005.txt')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        for info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001.htz'),
            os.path.join(self.test_output, '20200101000000002.htz'),
            os.path.join(self.test_output, '20200101000000003.htz'),
            os.path.join(self.test_output, '20200101000000004.html'),
            os.path.join(self.test_output, '20200101000000005.txt'),
            })

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000001.htz')) as zh:
            self.assertEqual(zh.namelist(), ['index.html', 'resource.txt'])

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000003.htz')) as zh:
            self.assertEqual(zh.namelist(), ['index.html', 'resource.txt'])

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001.htz')).st_mtime,
            )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000002.htz')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000002.htz')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000003.htz')).st_mtime,
                )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.htz',
                },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.htz',
                },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003.htz',
                },
            '20200101000000004': {
                'type': '',
                'index': '20200101000000004.html',
                },
            '20200101000000005': {
                'type': '',
                'index': '20200101000000005.txt',
                },
            })

    def test_param_format_htz02(self):
        """Check if icon path is correctly handled for folder => htz.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.ico"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.htz'),
            })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.ico'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.ico',
                },
            })

    def test_param_format_htz03(self):
        """Check if icon path is correctly handled for maff => htz.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.maff",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """my page content""")
            zh.writestr('20200101000000000/index.rdf', """dummy""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.htz'),
            })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/favicon.ico',
                },
            })

    def test_param_format_maff01(self):
        """Test format "maff"

        - MAFF converted from other format should contain a valid index.rdf
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000001/index.html"
  },
  "20200101000000002": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000002.htz"
  },
  "20200101000000003": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000003.maff"
  },
  "20200101000000004": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000004.html"
  },
  "20200101000000005": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000005.txt"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000001')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'resource.txt'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")
            zh.writestr('resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000003/index.html', """my page content""")
            zh.writestr('20200101000000003/index.rdf', """dummy""")
            zh.writestr('20200101000000003/resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        index_file = os.path.join(self.test_input, '20200101000000005.txt')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        for info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001.maff'),
            os.path.join(self.test_output, '20200101000000002.maff'),
            os.path.join(self.test_output, '20200101000000003.maff'),
            os.path.join(self.test_output, '20200101000000004.html'),
            os.path.join(self.test_output, '20200101000000005.txt'),
            })

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000001.maff')) as zh:
            self.assertEqual(set(zh.namelist()), {
                '20200101000000001/',
                '20200101000000001/index.html',
                '20200101000000001/index.rdf',
                '20200101000000001/resource.txt',
                })
            with zh.open('20200101000000001/index.rdf') as fh:
                dt = util.id_to_datetime('20200101000000000').astimezone()
                self.assertEqual(
                    util.parse_maff_index_rdf(fh),
                    ('', '', format_datetime(dt), 'index.html', 'UTF-8'),
                    )

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000002.maff')) as zh:
            self.assertEqual(set(zh.namelist()), {
                '20200101000000002/',
                '20200101000000002/index.html',
                '20200101000000002/index.rdf',
                '20200101000000002/resource.txt',
                })
            with zh.open('20200101000000002/index.rdf') as fh:
                dt = util.id_to_datetime('20200101000000000').astimezone()
                self.assertEqual(
                    util.parse_maff_index_rdf(fh),
                    ('', '', format_datetime(dt), 'index.html', 'UTF-8'),
                    )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001.maff')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000002.htz')) as zh:
            self.assertEqual(
                util.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002.maff')).st_mtime,
                )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000003.maff')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000003.maff')).st_mtime,
            )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.maff',
                'create': '20200101000000000',
                },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.maff',
                'create': '20200101000000000',
                },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003.maff',
                'create': '20200101000000000',
                },
            '20200101000000004': {
                'type': '',
                'index': '20200101000000004.html',
                'create': '20200101000000000',
                },
            '20200101000000005': {
                'type': '',
                'index': '20200101000000005.txt',
                'create': '20200101000000000',
                },
            })

    def test_param_format_maff02(self):
        """Fail if index.rdf already exists
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "index": "20200101000000001/index.html"
  },
  "20200101000000002": {
    "type": "",
    "index": "20200101000000002.htz"
  },
  "20200101000000003": {
    "type": "",
    "index": "20200101000000003.maff"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000001')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'index.rdf'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")
        with open(os.path.join(index_dir, 'resource.txt'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")
            zh.writestr('index.rdf', """dummy""")
            zh.writestr('resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000003/index.html', """my page content""")
            zh.writestr('20200101000000003/index.rdf', """dummy""")
            zh.writestr('20200101000000003/resource.txt', """dummy""")

        for info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
            os.path.join(self.test_output, '20200101000000001', 'index.rdf'),
            os.path.join(self.test_output, '20200101000000001', 'resource.txt'),
            os.path.join(self.test_output, '20200101000000002.htz'),
            os.path.join(self.test_output, '20200101000000003.maff'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.htz',
                },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003.maff',
                },
            })

    def test_param_format_maff03(self):
        """Check if icon path is correctly handled for folder => maff.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.ico"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.maff'),
            })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.ico'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.ico',
                },
            })

    def test_param_format_maff04(self):
        """Check if icon path is correctly handled for htz => maff.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.htz",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.maff'),
            })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
            })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/favicon.ico',
                },
            })

if __name__ == '__main__':
    unittest.main()
