from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
import io
import openpyxl

from races.models import Race, Result, Runner, Season


class TestFileUpload(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.season = Season.objects.create(season_start_year=2025)

        from django.contrib.auth.models import User
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def setUp(self):
        self.client.login(username='testuser', password='testpass123')

    def test_race_file_upload_creates_race(self):
        wb = openpyxl.Workbook()
        ws = wb.active

        ws.append(['First Name', 'Last Name', 'Participant Number',
                   'Category', 'Club', 'Time'])
        ws.append(['Lukasz', 'Pudlo', '121', 'MS', 'Unaffiliated', '00:19:31'])
        ws.append(['Callum', 'Wallace', '654', 'MS',
                   'Bellahouston Harriers', '00:20:51'])

        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        uploaded_file = SimpleUploadedFile(
            'test_kings.xlsx',
            excel_file.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        form_data = {
            'name': "Test King's Park",
            'season_start_year': 2025,
            'race_file': uploaded_file
        }

        # Post to the URL: /races/race/new/
        response = self.client.post('/races/race/new/', form_data)

        # Check that we got a redirect (302 status code means success)
        self.assertEqual(response.status_code, 302)

        # Check that the race was created
        self.assertEqual(Race.objects.count(), 1)

        # Verify the race has the correct data
        race = Race.objects.first()
        self.assertEqual(race.name, "Test King's Park")
        self.assertEqual(race.season_start_year, 2025)
