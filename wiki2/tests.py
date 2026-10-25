import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import constants
from .models import WikiPage, WikiFile


class ChunkedUploadTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()

        self.user = User.objects.create_user('alice', password='pw')
        self.page = WikiPage.objects.create(title='Docs', last_modified_by=self.user)
        self.client.force_login(self.user)
        self.init_url = reverse('wiki:page_upload_init', kwargs={'slug': self.page.slug})

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _init(self, size, filename='big file.bin', filename_slug=''):
        return self.client.post(
            self.init_url,
            data={'filename': filename, 'filename_slug': filename_slug, 'size': size},
            content_type='application/json',
        )

    def _chunk(self, upload_id, offset, data):
        url = reverse('wiki:page_upload_chunk', kwargs={'slug': self.page.slug, 'upload_id': upload_id})
        return self.client.post(url, data=data, content_type='application/octet-stream',
                                headers={'X-Upload-Offset': str(offset)})

    def _complete(self, upload_id):
        url = reverse('wiki:page_upload_complete', kwargs={'slug': self.page.slug, 'upload_id': upload_id})
        return self.client.post(url)

    def _staging_dir(self, upload_id):
        return os.path.join(self.media_root, constants.CHUNKED_UPLOAD_DIR_NAME, upload_id)

    def test_full_upload_in_chunks(self):
        payload = os.urandom(2500)
        upload_id = self._init(len(payload)).json()['upload_id']

        for offset in range(0, len(payload), 1000):
            response = self._chunk(upload_id, offset, payload[offset:offset + 1000])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['received'], min(offset + 1000, len(payload)))

        response = self._complete(upload_id)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()['file']
        self.assertEqual(file_data['filename_slug_stored'], 'big-file')
        self.assertEqual(file_data['uploaded_by_username'], 'alice')

        wiki_file = WikiFile.objects.get(pk=file_data['id'])
        self.assertEqual(wiki_file.page, self.page)
        self.assertEqual(wiki_file.file.name, 'wiki_files/docs/big-file.bin')
        with wiki_file.file.open('rb') as f:
            self.assertEqual(f.read(), payload)
        self.assertFalse(os.path.exists(self._staging_dir(upload_id)))

    def test_resent_chunk_is_idempotent(self):
        payload = b'a' * 10 + b'b' * 10
        upload_id = self._init(len(payload)).json()['upload_id']
        self._chunk(upload_id, 0, payload[:10])
        self._chunk(upload_id, 10, payload[10:])
        # Response to the last chunk got "lost"; the client sends it again.
        response = self._chunk(upload_id, 10, payload[10:])
        self.assertEqual(response.json()['received'], 20)
        self.assertEqual(self._complete(upload_id).status_code, 200)
        with WikiFile.objects.get().file.open('rb') as f:
            self.assertEqual(f.read(), payload)

    def test_offset_beyond_received_reports_position(self):
        upload_id = self._init(20).json()['upload_id']
        self._chunk(upload_id, 0, b'x' * 5)
        response = self._chunk(upload_id, 15, b'x' * 5)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['received'], 5)

    def test_chunk_larger_than_announced_size_is_rejected(self):
        upload_id = self._init(10).json()['upload_id']
        response = self._chunk(upload_id, 0, b'x' * 11)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(os.path.getsize(os.path.join(self._staging_dir(upload_id), 'data.part')), 0)

    def test_complete_before_all_data_fails(self):
        upload_id = self._init(10).json()['upload_id']
        self._chunk(upload_id, 0, b'x' * 4)
        response = self._complete(upload_id)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(WikiFile.objects.exists())

    def test_invalid_init_requests(self):
        self.assertEqual(self._init(0).status_code, 400)
        response = self._init(10, filename_slug='not a slug!')
        self.assertEqual(response.status_code, 400)
        self.assertIn('filename_slug', response.json()['errors'])

    def test_other_user_cannot_touch_upload(self):
        upload_id = self._init(10).json()['upload_id']
        self.client.force_login(User.objects.create_user('mallory', password='pw'))
        self.assertEqual(self._chunk(upload_id, 0, b'x' * 10).status_code, 404)
        self.assertEqual(self._complete(upload_id).status_code, 404)

    def test_cancel_removes_staging(self):
        upload_id = self._init(10).json()['upload_id']
        url = reverse('wiki:page_upload_cancel', kwargs={'slug': self.page.slug, 'upload_id': upload_id})
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertFalse(os.path.exists(self._staging_dir(upload_id)))

    def test_path_components_are_stripped_from_filename(self):
        upload_id = self._init(3, filename='..\\..\\evil.txt').json()['upload_id']
        self._chunk(upload_id, 0, b'abc')
        wiki_file = WikiFile.objects.get(pk=self._complete(upload_id).json()['file']['id'])
        self.assertEqual(wiki_file.file.name, 'wiki_files/docs/evil.txt')
