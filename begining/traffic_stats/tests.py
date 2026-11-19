from copy import copy
from datetime import date
from io import BytesIO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Subscriber, Channel, ImportBatch, Record
from .parser import parse, decode, ImportError

AFTN = 'AFTN\n01.05-31.05 2026\n079;РАМ;УЛЛЛЫФЫА;Монитор;65;97\nИТОГО:65;97'
AMHS = 'AMHS\n01.10.2026-31.10.2026\nMTA-UHPP-1;108;2'
def template_marker_row(sheet_name, marker):
    """Номер строки данных берём из текущего шаблона, который меняет пользователь."""
    from openpyxl import load_workbook
    from .monthly_export import TEMPLATE
    book = load_workbook(TEMPLATE)
    try:
        return next(cell.row for row in book[sheet_name] for cell in row
                    if isinstance(cell.value, str) and marker in cell.value)
    finally:
        book.close()

class ParserTests(TestCase):
    def test_formats_encodings_and_totals(self):
        for enc in ('utf-8-sig','cp1251'):
            p=parse(decode(AFTN.encode(enc)))
            self.assertEqual(p['month'],'2026-05-01')
            self.assertEqual(p['rows'][0]['number'],'079')
            self.assertEqual(set(p['rows'][0]) & {'service_received','service_sent'}, set())
        p=parse(AMHS)
        self.assertEqual(p['rows'][0]['received'],108)
        self.assertEqual(p['rows'][0]['sent'],2)
    def test_invalid_reports(self):
        for text in (AFTN.replace('31.05','30.05'),AFTN.replace(';65;97',';-1;97'), AMHS+'\nMTA-UHPP-1;108;2'):
            with self.assertRaises(ImportError): parse(text)
    def test_leap_month(self):
        self.assertEqual(parse(AFTN.replace('01.05-31.05 2026','01.02-29.02 2024'))['month'],'2024-02-01')

class WorkflowTests(TestCase):
    def preview(self,text=AFTN):
        return self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('sample.txt',text.encode('utf-8'))})
    def save(self,**extra):
        token=self.client.session['stats_preview']['token']
        return self.client.post('/statistics/upload/',dict(action='save',token=token,**extra))
    def test_mapping_replace_and_preserve_other_type(self):
        self.assertEqual(self.preview().status_code,200)
        self.save()
        self.assertEqual(ImportBatch.objects.count(),0)
        self.save(new_0='Центр',category_0='regional',name_0='Канал')
        self.assertEqual(Record.objects.count(),1)
        subscriber=Subscriber.objects.get()
        channel=Channel.objects.get()
        batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AMHS',filename='amhs',source=AMHS)
        amhs=Channel.objects.create(kind='AMHS',route_address='MTA',name='MTA',subscriber=subscriber)
        Record.objects.create(batch=batch,channel=amhs,received=10,sent=20)
        self.preview(AFTN.replace(';65;97',';66;97').replace('ИТОГО:65','ИТОГО:66'))
        self.save()
        self.assertEqual(Record.objects.get(channel=channel).received,65)
        self.save(replace='yes')
        self.assertEqual(Record.objects.get(channel=channel).received,66)
        self.assertEqual(Record.objects.get(channel=amhs).received,10)
        self.assertEqual(Channel.objects.get(pk=channel.pk).name,'Канал')
    def test_views_exports_and_text_cells(self):
        self.preview();self.save(new_0='=Центр',category_0='local',name_0='=Канал')
        for url in ('/statistics/','/statistics/directory/','/statistics/subscriber/1/','/statistics/channel/1/'):
            self.assertEqual(self.client.get(url).status_code,200)
        x=self.client.get('/statistics/?month=2026-05&export=xlsx')
        self.assertEqual(x.status_code,200)
        from openpyxl import load_workbook
        sheet=load_workbook(BytesIO(x.content)).active
        self.assertEqual(sheet['A5'].data_type,'s')
        self.assertEqual(sheet['B5'].value,65)
        self.assertEqual(sheet.max_column,4)
        self.assertEqual([c.value for c in sheet[4]], ['Абонент','Принято','Передано','Канал'])
        self.assertEqual(self.client.get('/statistics/?month=2026-05&kind=AMHS').context['totals'],{})

    def test_new_mappings_rollback_on_error(self):
        text=AFTN.replace('ИТОГО:65;97','080;РЦУ;УЛЛЛЫФЫЙ;Центр;3;4\nИТОГО:68;101')
        self.preview(text)
        self.save(new_0='Не сохранять частично')
        self.assertEqual(Subscriber.objects.count(),0)
        self.assertEqual(Channel.objects.count(),0)
        self.assertEqual(ImportBatch.objects.count(),0)

    def test_replace_removes_absent_channels(self):
        self.preview(AFTN)
        self.save(new_0='Центр')
        channel=Channel.objects.get()
        batch=ImportBatch.objects.get()
        other=Channel.objects.create(kind='AFTN',route_address='УЛЛЛЫФЫЙ',name='Другая линия',subscriber=channel.subscriber)
        Record.objects.create(batch=batch,channel=other,received=1,sent=2)
        self.preview(AFTN)
        self.save(replace='yes')
        self.assertEqual(Record.objects.count(),1)
        self.assertTrue(Channel.objects.filter(pk=other.pk).exists())


class AdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_superuser(username='stats-admin', password='test-password')
        self.client.force_login(self.user)

    def test_statistics_admin_pages(self):
        response = self.client.get('/admin/')
        self.assertContains(response, 'Статистика')
        self.assertContains(response, 'Абоненты')
        for model in ('subscriber', 'channel', 'importbatch', 'record'):
            self.assertEqual(self.client.get(f'/admin/traffic_stats/{model}/').status_code, 200)
        response = self.client.get('/admin/traffic_stats/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a['app_label'] for a in response.context['app_list']], ['traffic_stats'])

    def test_staff_with_only_statistics_permission(self):
        from django.contrib.auth.models import Permission
        self.user.is_superuser = False
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename='view_subscriber', content_type__app_label='traffic_stats'))
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.get('/admin/traffic_stats/').status_code, 200)


class AdminDeletionTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_superuser(username='delete-admin', password='test-password')
        self.client.force_login(self.user)
        self.subscriber = Subscriber.objects.create(name='Тестовый абонент')
        self.channel = Channel.objects.create(kind='AFTN', route_address='УЛЛЛЫФЫА', name='Канал', subscriber=self.subscriber)
        self.batch = ImportBatch.objects.create(month=date(2026, 5, 1), kind='AFTN', filename='test.txt', source=AFTN)
        self.record = Record.objects.create(batch=self.batch, channel=self.channel, received=65, sent=97)
        self.other_batch = ImportBatch.objects.create(month=date(2026, 6, 1), kind='AFTN', filename='other.txt', source='')
        self.other_record = Record.objects.create(batch=self.other_batch, channel=self.channel, received=1, sent=2)

    def test_delete_report_requires_confirmation_and_cascades_only_its_rows(self):
        url = f'/admin/traffic_stats/importbatch/{self.batch.pk}/delete/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(ImportBatch.objects.filter(pk=self.batch.pk).exists())
        self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 302)
        self.assertFalse(ImportBatch.objects.filter(pk=self.batch.pk).exists())
        self.assertFalse(Record.objects.filter(pk=self.record.pk).exists())
        self.assertTrue(Record.objects.filter(pk=self.other_record.pk).exists())
        self.assertTrue(Channel.objects.filter(pk=self.channel.pk).exists())
        self.assertTrue(Subscriber.objects.filter(pk=self.subscriber.pk).exists())

    def test_bulk_delete_rows_preserves_report_and_directory(self):
        url = '/admin/traffic_stats/record/'
        data = {'action': 'delete_selected', '_selected_action': [str(self.record.pk)]}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertTrue(Record.objects.filter(pk=self.record.pk).exists())
        data['post'] = 'yes'
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertFalse(Record.objects.filter(pk=self.record.pk).exists())
        self.assertTrue(ImportBatch.objects.filter(pk=self.batch.pk).exists())
        self.assertTrue(Record.objects.filter(pk=self.other_record.pk).exists())
        self.assertTrue(Channel.objects.filter(pk=self.channel.pk).exists())

    def test_delete_channel_confirms_and_removes_its_statistics_for_all_months(self):
        other_channel=Channel.objects.create(kind='AFTN',route_address='OTHER001',name='Другой канал',subscriber=self.subscriber)
        untouched=Record.objects.create(batch=self.batch,channel=other_channel,received=3,sent=4)
        self.record.user_received=0
        self.record.save()
        url=f'/admin/traffic_stats/channel/{self.channel.pk}/delete/'
        page=self.client.get(url)
        self.assertEqual(page.status_code,200)
        self.assertFalse(page.context['protected'])
        self.assertFalse(page.context['perms_lacking'])
        self.assertTrue(Record.objects.filter(pk=self.record.pk).exists())
        self.assertEqual(self.client.post(url,{'post':'yes'}).status_code,302)
        self.assertFalse(Channel.objects.filter(pk=self.channel.pk).exists())
        self.assertFalse(Record.objects.filter(channel_id=self.channel.pk).exists())
        self.assertTrue(Record.objects.filter(pk=untouched.pk).exists())
        self.assertTrue(Subscriber.objects.filter(pk=self.subscriber.pk).exists())
        self.assertEqual(ImportBatch.objects.count(),2)

    def test_bulk_delete_channels_also_deletes_statistics(self):
        data={'action':'delete_selected','_selected_action':[str(self.channel.pk)]}
        page=self.client.post('/admin/traffic_stats/channel/',data)
        self.assertEqual(page.status_code,200)
        self.assertTrue(Channel.objects.filter(pk=self.channel.pk).exists())
        data['post']='yes'
        self.assertEqual(self.client.post('/admin/traffic_stats/channel/',data).status_code,302)
        self.assertFalse(Channel.objects.filter(pk=self.channel.pk).exists())
        self.assertEqual(Record.objects.count(),0)
        self.assertEqual(ImportBatch.objects.count(),2)

    def test_view_only_staff_cannot_delete(self):
        from django.contrib.auth.models import Permission
        self.user.is_superuser = False
        self.user.save()
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='traffic_stats', codename__in=['view_record', 'view_importbatch']))
        for model, pk in [('importbatch', self.batch.pk), ('record', self.record.pk)]:
            self.assertEqual(self.client.post(f'/admin/traffic_stats/{model}/{pk}/delete/', {'post': 'yes'}).status_code, 403)
        self.assertTrue(Record.objects.filter(pk=self.record.pk).exists())
        self.assertTrue(ImportBatch.objects.filter(pk=self.batch.pk).exists())


class SubscriberDefaultsTests(TestCase):
    def test_preview_prefills_subscriber_from_aftn_and_amhs_names(self):
        for text, expected in [(AFTN, 'Монитор'), (AMHS, 'MTA-UHPP-1')]:
            response = self.client.post('/statistics/upload/', {'action': 'preview', 'file': SimpleUploadedFile('sample.txt', text.encode('utf-8'))})
            self.assertContains(response, f'name="new_0" value="{expected}"')
            token = self.client.session['stats_preview']['token']
            self.client.post('/statistics/upload/', {'action':'save', 'token':token, 'new_0':expected})
            self.assertTrue(Subscriber.objects.filter(name=expected).exists())

    def test_comment_editable_in_admin_but_not_public_form(self):
        from django.contrib.auth import get_user_model
        from .forms import SubscriberForm
        subscriber = Subscriber.objects.create(name='Абонент')
        self.assertNotIn('comment', SubscriberForm().fields)
        user = get_user_model().objects.create_superuser(username='comment-admin', password='test-password')
        self.client.force_login(user)
        url = f'/admin/traffic_stats/subscriber/{subscriber.pk}/change/'
        self.assertContains(self.client.get(url), 'name="comment"')
        response = self.client.post(url, {'name':subscriber.name, 'category':'other', 'comment':'Заметка пользователя', 'channels-TOTAL_FORMS':'0', 'channels-INITIAL_FORMS':'0', '_save':'Сохранить'})
        self.assertEqual(response.status_code, 302)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.comment, 'Заметка пользователя')
        self.assertNotContains(self.client.get(f'/statistics/subscriber/{subscriber.pk}/'), 'name="comment"')
        self.assertNotContains(self.client.get('/statistics/directory/'), 'Заметка пользователя')


class IgnoredAftnTotalsTests(TestCase):
    def test_missing_wrong_or_repeated_totals_are_ignored(self):
        base = AFTN.split('ИТОГО:')[0]
        expected = parse(base)
        for suffix in ('', 'ИТОГО:0;0;0;0', 'ИТОГО:не число', 'ИТОГО:1\nИТОГО:2'):
            self.assertEqual(parse(base + suffix), expected)

    def test_totals_not_saved_in_source_or_records(self):
        response = self.client.post('/statistics/upload/', {'action':'preview', 'file':SimpleUploadedFile('aftn.txt', AFTN.encode('utf-8'))})
        self.assertEqual(response.status_code, 200)
        payload = self.client.session['stats_preview']
        self.assertNotIn('ИТОГО', payload['source'])
        self.client.post('/statistics/upload/', {'action':'save', 'token':payload['token'], 'new_0':'Монитор'})
        self.assertEqual(Record.objects.count(), 1)
        self.assertNotIn('ИТОГО', ImportBatch.objects.get().source)
        self.assertEqual(Record.objects.get().received, 65)


class ChannelMetadataAndPeriodTests(TestCase):
    def setUp(self):
        self.subscriber = Subscriber.objects.create(name='Центр')
        self.channel = Channel.objects.create(kind='AFTN',route_address='УЛЛЛЫФЫА',name='Монитор',subscriber=self.subscriber)
        for month, count in [(date(2025,12,1),10),(date(2026,1,1),20),(date(2026,2,1),40)]:
            batch = ImportBatch.objects.create(month=month,kind='AFTN',filename='month.txt',source='')
            Record.objects.create(batch=batch,channel=self.channel,received=count,sent=count*2)

    def test_range_sums_same_channel_and_single_month_still_works(self):
        response = self.client.get('/statistics/?month=2025-12&end_month=2026-01')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['totals']['AFTN']['received'],30)
        self.assertEqual(len(response.context['groups'][0]['rows']),1)
        self.assertEqual(response.context['groups'][0]['rows'][0].sent,60)
        self.assertEqual(self.client.get('/statistics/?month=2026-02').context['totals']['AFTN']['received'],40)
        self.assertEqual(Record.objects.for_period(date(2025,12,15),date(2026,1,31)).count(),2)
        self.assertEqual(self.client.get('/statistics/?month=2026-02&end_month=2025-12').status_code,400)
        self.assertEqual(self.client.get('/statistics/?month=bad').status_code,400)
        self.assertEqual(self.client.get('/statistics/?month=2024-01&end_month=2024-12').context['groups'],[])

    def test_import_metadata_and_upload_date(self):
        response = self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('test.txt',AFTN.encode('utf-8'))})
        token = self.client.session['stats_preview']['token']
        self.assertEqual(response.status_code,200)
        response = self.client.post('/statistics/upload/',{'action':'save','token':token})
        self.assertEqual(response.status_code,302)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.logical_number,79)
        self.assertEqual(self.channel.transmission_designation,'РАМ')
        row = Record.objects.get(batch__month=date(2026,5,1))
        self.assertFalse(hasattr(row, 'uploaded_at'))
        self.assertIsNotNone(row.batch.imported_at)
        self.assertEqual(row.received,65)
        self.assertFalse(hasattr(row,'source_name'))
        self.assertFalse(hasattr(row,'number'))
        self.assertFalse(hasattr(row,'designation'))
        self.assertEqual(self.channel.name,'Монитор')

    def test_range_exports_match_screen(self):
        url = '/statistics/?month=2025-12&end_month=2026-01&export='
        from openpyxl import load_workbook
        response = self.client.get(url+'xlsx')
        self.assertEqual(response.status_code,200)
        sheet = load_workbook(BytesIO(response.content)).active
        self.assertEqual(sheet['B5'].value,30)
        self.assertEqual(sheet['A1'].value,'Статистика по каналам за декабрь 2025 — январь 2026')
        self.assertIn('2025-12-to-2026-01',response['Content-Disposition'])


from django.test import TransactionTestCase
class MetadataMigrationTests(TransactionTestCase):
    def test_existing_records_are_moved_before_removal(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        previous = ('traffic_stats','0003_subscriber_comment')
        target = ('traffic_stats','0004_remove_record_designation_remove_record_number_and_more')
        executor = MigrationExecutor(connection)
        executor.migrate([previous])
        try:
            apps = executor.loader.project_state([previous]).apps
            subscriber = apps.get_model('traffic_stats','Subscriber').objects.create(name='Миграция')
            channel = apps.get_model('traffic_stats','Channel').objects.create(kind='AFTN',system_name='УЛЛЛЫФЫА',name='Пользовательское имя',subscriber=subscriber)
            batch = apps.get_model('traffic_stats','ImportBatch').objects.create(month=date(2026,5,1),kind='AFTN',filename='old.txt',source='')
            row = apps.get_model('traffic_stats','Record').objects.create(batch=batch,channel=channel,number='079',designation='РАМ',source_name='Имя из файла',received=65,sent=97)
            executor = MigrationExecutor(connection)
            executor.migrate([target])
            apps = executor.loader.project_state([target]).apps
            saved_channel = apps.get_model('traffic_stats','Channel').objects.get(pk=channel.pk)
            saved_record = apps.get_model('traffic_stats','Record').objects.get(pk=row.pk)
            self.assertEqual(saved_channel.logical_number,79)
            self.assertEqual(saved_channel.transmission_designation,'РАМ')
            self.assertEqual(saved_channel.name,'Пользовательское имя')
            self.assertEqual(saved_record.received,65)
            self.assertEqual(saved_record.uploaded_at,batch.imported_at)
        finally:
            final_executor = MigrationExecutor(connection)
            final_executor.migrate(final_executor.loader.graph.leaf_nodes())


class CompactAftnAndReportMonthTests(TestCase):
    def test_typed_format_matches_fixture(self):
        compact = 'AFTN\n01.05-31.05 2026\n079;РАМ;УЛЛЛЫФЫА;Монитор;65;97\n'
        self.assertEqual(parse(compact),parse(AFTN))
        self.assertEqual(parse(compact+'ИТОГО:не обрабатывать'),parse(compact))
        for text in (compact.replace('31.05','30.05'),compact.replace('31.05','31.06')):
            with self.assertRaises(ImportError): parse(text)

    def test_report_month_is_saved_and_admin_omits_day(self):
        from django.contrib.auth import get_user_model
        compact = 'AFTN\n01.05-31.05 2026\n079;РАМ;УЛЛЛЫФЫА;Монитор;65;97\n'
        self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('aftn.txt',compact.encode('utf-8'))})
        token = self.client.session['stats_preview']['token']
        self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':'Монитор'})
        record = Record.objects.get()
        self.assertEqual(record.report_month,date(2026,5,1))
        self.assertEqual(Record.objects.for_period(date(2026,5,1)).count(),1)
        self.assertNotIn('JOIN',str(Record.objects.for_period(date(2026,5,1)).query))
        user = get_user_model().objects.create_superuser(username='period-admin',password='test-password')
        self.client.force_login(user)
        for url in ['/admin/traffic_stats/importbatch/', f'/admin/traffic_stats/importbatch/{record.batch_id}/change/', '/admin/traffic_stats/record/']:
            response = self.client.get(url)
            self.assertContains(response,'Май 2026')
            self.assertNotContains(response,'1 мая 2026')


class TypedReportTests(TestCase):
    def test_type_header_and_column_counts_are_validated(self):
        for text in (AFTN.replace('AFTN\n','',1), AFTN.replace('AFTN','OTHER',1), AFTN.replace(';65;97',';65;97;63;58'), AMHS.replace('AMHS','AFTN',1), AMHS.replace('31.10.2026','31.10.2025')):
            with self.assertRaises(ImportError):
                parse(text)

    def test_only_general_counts_in_preview_report_and_admin(self):
        response = self.client.post('/statistics/upload/', {'action':'preview','file':SimpleUploadedFile('aftn.txt',AFTN.encode('utf-8'))})
        self.assertNotContains(response,'Служ.')
        token = self.client.session['stats_preview']['token']
        self.client.post('/statistics/upload/', {'action':'save','token':token,'new_0':'Монитор'})
        self.assertNotContains(self.client.get('/statistics/'),'Служ.')
        fields = {f.name for f in Record._meta.fields}
        self.assertNotIn('service_received',fields)
        self.assertNotIn('service_sent',fields)


class LatestStatisticsLinkTests(TestCase):
    def test_no_statistics_shows_text_without_link(self):
        for url in ['/statistics/', '/statistics/directory/']:
            response = self.client.get(url)
            self.assertContains(response, '(последней статистики не найдено)')
            self.assertNotContains(response, 'последняя статистика за период')

    def test_link_uses_latest_report_month_and_resets_filters(self):
        subscriber = Subscriber.objects.create(name='Последний абонент')
        channel = Channel.objects.create(kind='AFTN',route_address='УЛЛЛЫФЫА',name='Канал',subscriber=subscriber)
        for month, count in [(date(2026,10,1),100),(date(2026,5,1),50)]:
            batch = ImportBatch.objects.create(month=month,kind='AFTN',filename='test.txt',source='')
            Record.objects.create(batch=batch,channel=channel,received=count,sent=count)
        initial = self.client.get('/statistics/')
        self.assertEqual(initial.context['groups'], [])
        self.assertEqual(initial.context['totals'], {})
        self.assertNotContains(initial, 'Итоги выборки')
        self.assertNotContains(initial, 'Нет данных для выбранных фильтров.')
        self.assertEqual(initial.context['latest_statistics'], date(2026,10,1))
        # An empty import must not be advertised as available statistics.
        ImportBatch.objects.create(month=date(2026,12,1),kind='AFTN',filename='empty.txt',source='')
        response = self.client.get('/statistics/?month=2026-05&kind=AMHS')
        self.assertContains(response, 'октябрь 2026 г.)')
        self.assertContains(response, 'href="/statistics/?month=2026-10&amp;end_month=2026-10"')
        latest = self.client.get('/statistics/?month=2026-10&end_month=2026-10')
        self.assertEqual(latest.context['totals']['AFTN']['received'],100)


class StatisticsNavigationTests(TestCase):
    def test_statistics_is_the_only_report_screen(self):
        page=self.client.get('/statistics/')
        self.assertContains(page,'href="/statistics/?period=1">Статистика</a>')
        self.assertContains(page,'>Загрузить статистику</a>')
        self.assertNotContains(page,'>Отчёты</a>')
        self.assertNotContains(page,'filters=1')
        self.assertNotContains(page,'name="kind"')
        self.assertNotContains(page,'name="category"')
        self.assertNotContains(page,'name="subscriber"')
        self.assertContains(page,'class="filters toolbar-period"')
        self.assertFalse(page.context['report_requested'])

    def test_legacy_reports_url_redirects_to_statistics_preserving_period(self):
        response=self.client.get('/statistics/?filters=1&month=2026-05&end_month=2026-06')
        self.assertRedirects(response,'/statistics/?month=2026-05&end_month=2026-06&period=1')
        page=self.client.get('/statistics/?filters=1&month=2026-05',follow=True)
        self.assertTrue(page.context['report_requested'])
        self.assertNotContains(page,'export=xlsx')
        self.assertNotContains(page,'name="filters"')


class PeriodPickerAssetsTests(TestCase):
    def test_calendar_loads_only_with_filters_and_native_fields_remain(self):
        for url in ['/statistics/upload/', '/statistics/directory/']:
            self.assertNotContains(self.client.get(url), 'air-datepicker.js')
        response = self.client.get('/statistics/?period=1&month=2025-12&end_month=2026-02')
        self.assertContains(response, '/static/traffic_stats/vendor/air-datepicker-3.6.0/air-datepicker.js')
        self.assertContains(response, '/static/traffic_stats/vendor/air-datepicker-3.6.0/air-datepicker.css')
        self.assertContains(response, 'type="month" name="month" value="2025-12" required')
        self.assertContains(response, 'type="month" name="end_month" value="2026-02"')
        self.assertContains(response, 'class="stats-period-picker" hidden')
        self.assertNotContains(response, 'cdn.jsdelivr.net')


class CategoryReportTests(TestCase):
    def setUp(self):
        self.batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='test.txt',source='')
        self.subscribers={}
        for index, category in enumerate(['other','local','regional','international','federal']):
            sub=Subscriber.objects.create(name='Имя пользователя '+category,category=category)
            self.subscribers[category]=sub
            channel=Channel.objects.create(kind='AFTN',route_address=f'ADDR{index:04d}',name='Системное название',subscriber=sub)
            Record.objects.create(batch=self.batch,channel=channel,received=10,sent=20)
        extra=Channel.objects.create(kind='AFTN',route_address='EXTRA001',name='Второй канал',subscriber=self.subscribers['federal'])
        Record.objects.create(batch=self.batch,channel=extra,received=3,sent=4)
        amhs_batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AMHS',filename='amhs.txt',source='')
        amhs=Channel.objects.create(kind='AMHS',route_address='MTA-FED',name='AMHS',subscriber=self.subscribers['federal'])
        Record.objects.create(batch=amhs_batch,channel=amhs,received=7,sent=8)

    def test_category_order_subscriber_summary_and_channel_rows(self):
        response=self.client.get('/statistics/?month=2026-05')
        sections=response.context['category_sections']
        self.assertEqual([s['category'] for s in sections],['federal','international','regional','local','other'])
        entry=sections[0]['subscribers'][0]
        self.assertEqual((entry['received'],entry['sent']),(20,32))
        self.assertEqual(entry['address'],'')
        self.assertEqual(len(entry['channels']),3)
        self.assertEqual(sections[0]['totals'],{'received':20,'sent':32})
        self.assertEqual(len(sections[0]['subscribers']),1)
        self.assertEqual(sections[0]['first_column'],'Центр')
        self.assertEqual(sections[-1]['first_column'],'Абонент')
        from .reporting import report_rows
        rows=report_rows(response.context)
        details=[values for kind,values in rows if kind=='channel']
        self.assertEqual(len(details),3)
        self.assertTrue(all(row[0]=='' for row in details))
        self.assertEqual([r[3] for r in details],['ADDR0004','EXTRA001','AMHS'])
        self.assertContains(response,'Имя пользователя federal')
        self.assertNotContains(response,'Системное название')

    def test_filters_and_four_column_exports(self):
        response=self.client.get('/statistics/?month=2026-05&category=local')
        self.assertEqual(len(response.context['category_sections']),1)
        self.assertEqual(response.context['category_sections'][0]['first_column'],'Абонент')
        from openpyxl import load_workbook
        response=self.client.get('/statistics/?month=2026-05&kind=AFTN&category=federal&export=xlsx')
        sheet=load_workbook(BytesIO(response.content)).active
        self.assertEqual(sheet.max_column,4)
        self.assertEqual(sheet['A3'].value,'Федеральные каналы')
        self.assertEqual([c.value for c in sheet[4]],['Центр','Принято','Передано','Канал'])
        self.assertEqual(sheet['A5'].value,'Имя пользователя federal')
        self.assertEqual(sheet['B5'].value,13)
        self.assertEqual(sheet['B8'].value,13)
        self.assertIsNone(sheet['A6'].value)
        self.assertEqual(sheet['D6'].value,'ADDR0004')
        combined=self.client.get('/statistics/?month=2026-05&category=federal&export=xlsx')
        combined_sheet=load_workbook(BytesIO(combined.content)).active
        self.assertEqual(combined_sheet['B5'].value,20)
        self.assertEqual(combined_sheet['C5'].value,32)
        self.assertEqual(combined_sheet['B9'].value,20)
        self.assertEqual(combined_sheet['D8'].value,'AMHS')


class RouteAddressMigrationTests(TransactionTestCase):
    def test_rename_preserves_addresses_and_statistics(self):
        from django.db import connection, IntegrityError, transaction
        from django.db.migrations.executor import MigrationExecutor
        old=('traffic_stats','0007_remove_record_service_received_and_more')
        new=('traffic_stats','0008_channel_route_address')
        executor=MigrationExecutor(connection)
        executor.migrate([old])
        try:
            apps=executor.loader.project_state([old]).apps
            sub=apps.get_model('traffic_stats','Subscriber').objects.create(name='Перенос адреса')
            channel=apps.get_model('traffic_stats','Channel').objects.create(kind='AFTN',system_name='УЛЛЛЫФЫА',name='Пользовательское имя',subscriber=sub)
            batch=apps.get_model('traffic_stats','ImportBatch').objects.create(month=date(2026,5,1),kind='AFTN',filename='old.txt',source='')
            record=apps.get_model('traffic_stats','Record').objects.create(batch=batch,channel=channel,report_month=date(2026,5,1),received=123,sent=456)
            executor=MigrationExecutor(connection);executor.migrate([new])
            apps=executor.loader.project_state([new]).apps
            ChannelModel=apps.get_model('traffic_stats','Channel')
            saved=ChannelModel.objects.get(pk=channel.pk)
            self.assertEqual(saved.route_address,'УЛЛЛЫФЫА')
            self.assertEqual(saved.name,'Пользовательское имя')
            row=apps.get_model('traffic_stats','Record').objects.get(pk=record.pk)
            self.assertEqual((row.channel_id,row.received,row.sent),(channel.pk,123,456))
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    ChannelModel.objects.create(kind='AFTN',route_address='УЛЛЛЫФЫА',name='Дубль',subscriber_id=sub.pk)
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())


class CounterCorrectionTests(TestCase):
    def setUp(self):
        self.batch = ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='counts.txt',source='')
        self.sub = Subscriber.objects.create(name='Центр корректировки',category='federal')
        self.channel = Channel.objects.create(kind='AFTN',route_address='ADDRESS1',name='Канал',subscriber=self.sub)
        self.record = Record.objects.create(batch=self.batch,channel=self.channel,received=10,sent=20)
        self.url = f'/statistics/record/{self.record.pk}/correct/'

    def correct(self, **changes):
        data = dict(field='received',value='15',expected='10',month='2026-05')
        data.update(changes)
        return self.client.post(self.url,data)

    def test_override_zero_restore_original_and_independent_fields(self):
        self.assertIsNone(self.record.user_received)
        self.assertEqual(self.correct(value='0').status_code,200)
        self.record.refresh_from_db()
        self.assertEqual((self.record.received,self.record.sent),(10,20))
        self.assertEqual((self.record.effective_received,self.record.effective_sent),(0,20))
        self.assertEqual(self.correct(field='sent',value='25',expected='20').status_code,200)
        self.record.refresh_from_db()
        self.assertEqual((self.record.user_received,self.record.user_sent),(0,25))
        result = self.correct(value='10',expected='0')
        self.assertFalse(result.json()['overridden'])
        self.record.refresh_from_db()
        self.assertIsNone(self.record.user_received)
        self.assertEqual(self.record.effective_received,10)
        self.assertEqual(self.record.user_sent,25)

    def test_validation_wrong_month_deleted_record_and_conflict(self):
        for value in ('','-1','1.5','1e3','abc','9223372036854775808','9'*20):
            with self.subTest(value=value):
                self.assertEqual(self.correct(value=value).status_code,400)
        self.assertEqual(self.correct(field='user_received').status_code,400)
        self.assertEqual(self.correct(month='2026-05 - 2026-06').status_code,400)
        self.assertEqual(self.correct(month='2026-13').status_code,400)
        self.assertEqual(self.correct(month='2026-06').status_code,404)
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.assertEqual(self.correct().status_code,200)
        self.assertEqual(self.correct(value='99').status_code,409)
        self.record.refresh_from_db()
        self.assertEqual(self.record.user_received,15)
        self.record.delete()
        self.assertEqual(self.correct().status_code,404)

    def test_csrf_protection(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True)
        data=dict(field='received',value='15',expected='10',month='2026-05')
        self.assertEqual(client.post(self.url,data).status_code,403)
        page=client.get('/statistics/?month=2026-05')
        self.assertContains(page,'csrfmiddlewaretoken')
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url,data,HTTP_X_CSRFTOKEN=token).status_code,200)

    def test_edit_only_monthly_leaf_rows(self):
        page=self.client.get('/statistics/?month=2026-05')
        self.assertTrue(page.context['can_edit'])
        self.assertContains(page,' editable-stat',count=2)
        self.assertContains(page,'data-correction-url="'+self.url+'"',count=2)
        extra=Channel.objects.create(kind='AFTN',route_address='ADDRESS2',name='Второй',subscriber=self.sub)
        Record.objects.create(batch=self.batch,channel=extra,received=3,sent=4)
        page=self.client.get('/statistics/?month=2026-05')
        self.assertContains(page,' editable-stat',count=4)
        entry=page.context['category_sections'][0]['subscribers'][0]
        self.assertIsNone(entry['record'])
        self.assertTrue(all(row.record for row in entry['channels']))
        page=self.client.get('/statistics/?month=2026-05&end_month=2026-06')
        self.assertFalse(page.context['can_edit'])
        self.assertNotContains(page,' editable-stat')
        self.assertNotContains(page,'corrections.js')
        self.assertNotContains(page,'class="stat-editor"')

    def test_corrected_subscriber_totals_ranges_and_exports(self):
        from openpyxl import load_workbook
        extra=Channel.objects.create(kind='AFTN',route_address='ADDRESS2',name='Второй',subscriber=self.sub)
        Record.objects.create(batch=self.batch,channel=extra,received=3,sent=4)
        self.assertEqual(self.correct(value='100').status_code,200)
        monthly=self.client.get('/statistics/?month=2026-05')
        section=monthly.context['category_sections'][0]
        self.assertEqual(section['totals'],dict(received=103,sent=24))
        self.assertEqual(section['subscribers'][0]['received'],103)
        june=ImportBatch.objects.create(month=date(2026,6,1),kind='AFTN',filename='june',source='')
        Record.objects.create(batch=june,channel=self.channel,received=7,sent=9,user_sent=0)
        ranged=self.client.get('/statistics/?month=2026-05&end_month=2026-06')
        self.assertEqual(ranged.context['category_sections'][0]['totals'],dict(received=110,sent=24))
        self.assertContains(monthly, 'class="channel-row"', count=2)
        self.assertNotContains(ranged, 'class="channel-row"')
        self.assertContains(ranged, 'class="stat-month-toggle"', count=1)
        self.assertContains(ranged, 'class="stat-month-row" hidden', count=2)
        self.assertNotContains(monthly, 'class="stat-month-toggle"')
        months = ranged.context['category_sections'][0]['subscribers'][0]['monthly_totals']
        self.assertEqual(months, [
            {'label': 'май 2026', 'received': 103, 'sent': 24},
            {'label': 'июнь 2026', 'received': 7, 'sent': 0},
        ])
        printed = self.client.get('/statistics/?month=2026-05&end_month=2026-06&print=period')
        self.assertNotContains(printed, 'ADDRESS2')
        self.assertContains(printed, '<td class="period-number">110</td>', html=True)
        exported=self.client.get('/statistics/?month=2026-05&export=xlsx')
        sheet=load_workbook(BytesIO(exported.content)).active
        self.assertEqual(sheet['B5'].value,103)
        self.assertEqual(sheet['B6'].value,100)
        self.assertEqual(sheet['B8'].value,103)
        ranged_export=self.client.get('/statistics/?month=2026-05&end_month=2026-06&export=xlsx')
        sheet=load_workbook(BytesIO(ranged_export.content)).active
        self.assertEqual((sheet['B5'].value,sheet['C5'].value),(110,24))
        self.assertIs(sheet.sheet_properties.outlinePr.summaryBelow, False)
        self.assertTrue(sheet.row_dimensions[5].collapsed)
        self.assertFalse(sheet.row_dimensions[5].hidden)
        self.assertEqual([tuple(cell.value for cell in sheet[i][:3]) for i in (6, 7)],
                         [('май 2026', 103, 24), ('июнь 2026', 7, 0)])
        for index in (6, 7):
            self.assertTrue(sheet.row_dimensions[index].hidden)
            self.assertEqual(sheet.row_dimensions[index].outlineLevel, 1)
        self.assertEqual(sheet['A8'].value, 'Итого')
        self.assertFalse(sheet.row_dimensions[8].hidden)

    def test_exact_large_integer(self):
        value='9007199254740993'
        response=self.correct(value=value)
        self.assertEqual(response.json()['value'],value)
        self.record.refresh_from_db()
        self.assertEqual(self.record.user_received,int(value))
        page=self.client.get('/statistics/?month=2026-05')
        self.assertContains(page,'data-value="'+value+'"')


    def test_undo_icon_restores_imported_value(self):
        from html.parser import HTMLParser
        class Buttons(HTMLParser):
            def __init__(self, html):
                super().__init__()
                self.undo=[]
                self.feed(html)
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                if tag=='button' and attrs.get('class')=='stat-undo':
                    self.undo.append(attrs)
        def visible_undo():
            page=self.client.get('/statistics/?month=2026-05')
            return [b for b in Buttons(page.content.decode()).undo if 'hidden' not in b]
        self.assertEqual(visible_undo(),[])
        self.correct(value='0')
        buttons=visible_undo()
        self.assertEqual(len(buttons),1)
        self.assertEqual(buttons[0]['title'],'Прежнее значение: 10. Вернуть')
        self.assertEqual(self.correct(value='10',expected='0').status_code,200)
        self.assertEqual(visible_undo(),[])
        self.record.refresh_from_db()
        self.assertIsNone(self.record.user_received)
        self.assertEqual(self.record.received,10)


    def test_information_icon_for_saved_correction(self):
        from html.parser import HTMLParser
        class Information(HTMLParser):
            def __init__(self, html):
                super().__init__()
                self.visible=[]
                self.feed(html)
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                if tag=='span' and attrs.get('class')=='stat-info' and 'hidden' not in attrs:
                    self.visible.append(attrs)
        def info():
            return Information(self.client.get('/statistics/?month=2026-05').content.decode()).visible
        self.assertEqual(info(),[])
        self.assertNotContains(self.client.get('/statistics/?month=2026-05'),'title="Исходное значение:')
        self.correct(value='15')
        self.assertEqual(len(info()),1)
        self.assertNotIn('title',info()[0])
        self.assertContains(self.client.get('/statistics/?month=2026-05'),'title="Исходное значение: 10"',count=1)
        self.correct(value='10',expected='15')
        self.assertEqual(info(),[])
        self.assertNotContains(self.client.get('/statistics/?month=2026-05'),'title="Исходное значение:')


    def test_report_title_uses_month_names_and_matches_export(self):
        from openpyxl import load_workbook
        for query, title in [
            ('month=2026-05','Статистика по каналам за май 2026'),
            ('month=2026-05&end_month=2027-01','Статистика по каналам за май 2026 — январь 2027'),
        ]:
            page=self.client.get('/statistics/?'+query)
            self.assertContains(page,'<h2>'+title+'</h2>',html=True)
            sheet=load_workbook(BytesIO(self.client.get('/statistics/?'+query+'&export=xlsx').content)).active
            self.assertEqual(sheet['A1'].value,title)


class ToolbarPeriodTests(TestCase):
    def test_period_menu_opens_toolbar_and_submits_range(self):
        initial=self.client.get('/statistics/')
        self.assertContains(initial,'href="/statistics/?period=1"')
        self.assertContains(initial,'class="filters toolbar-period"')
        page=self.client.get('/statistics/?period=1')
        self.assertTrue(page.context['show_period'])
        self.assertFalse(page.context['report_requested'])
        self.assertContains(page,'class="filters toolbar-period"')
        self.assertContains(page,'name="period" value="1"')
        self.assertContains(page,'<input type="submit" value="Показать">',html=True)
        self.assertContains(page,'air-datepicker.js')
        self.assertContains(page,'type="month" name="month"')
        self.assertNotContains(page,'name="kind"')
        self.assertNotContains(page,'name="subscriber"')
        page=self.client.get('/statistics/?period=1&month=2026-05&end_month=2026-10')
        self.assertTrue(page.context['report_requested'])
        self.assertTrue(page.context['show_period'])
        self.assertContains(page,'value="2026-05"')
        self.assertContains(page,'value="2026-10"')
        self.assertContains(page,'Статистика по каналам за май 2026 — октябрь 2026')
        page=self.client.get('/statistics/?filters=1&period=1',follow=True)
        self.assertNotContains(page,'name="kind"')
        self.assertContains(page,'id="report-period"',count=1)


class UploadToolbarTests(TestCase):
    def test_upload_heading_description_and_toolbar(self):
        response=self.client.get('/statistics/upload/')
        self.assertContains(response,'<h1 class="stats-heading">Загрузка статистики</h1>',html=True)
        self.assertContains(response,'<h5>Текстовый файл AFTN или AMHS за полный месяц.</h5>',html=True)
        self.assertContains(response,'class="stats-upload toolbar-upload"',count=1)
        self.assertContains(response,'enctype="multipart/form-data"')
        self.assertContains(response,'type="file" name="file"')
        self.assertContains(response,'<input type="submit" value="Загрузить">',html=True)
        self.assertContains(response, 'id="statistics-text"')
        self.assertContains(response, 'После вставки нажмите «Загрузить».')
        self.assertNotContains(response,'Проверить файл')
        self.assertNotContains(response,'(последняя')
        html=response.content.decode()
        self.assertLess(html.index('Загрузка статистики</h1>'),html.index('id="toolbar"'))
        self.assertLess(html.index('id="toolbar"'),html.index('type="file" name="file"'))


class UploadPreviewLayoutTests(TestCase):
    def preview(self, text=AFTN):
        return self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('stats.txt',text.encode('utf-8'))})

    def test_flat_columns_defaults_and_save(self):
        page=self.preview()
        self.assertContains(page,'<th>Канал</th><th class="upload-designation">ПРД</th><th class="numeric">Принято</th><th class="numeric">Передано</th><th>Абонент</th><th class="upload-status-cell" aria-hidden="true"></th><th>Категория</th>',html=True)
        self.assertContains(page,'name="new_0" value="Монитор"')
        self.assertContains(page,'title="Новый канал"',count=1)
        self.assertContains(page,'<option value="other" selected>Прочие</option>',html=True)
        self.assertNotContains(page,'name="subscriber_0"')
        self.assertNotContains(page,'name="name_0"')
        token=self.client.session['stats_preview']['token']
        page=self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':'Пользовательское имя','category_0':'regional'})
        self.assertEqual(page.status_code,302)
        sub=Subscriber.objects.get()
        self.assertEqual((sub.name,sub.category),('Пользовательское имя','regional'))
        self.assertEqual(Channel.objects.get().name,'Монитор')
        page=self.preview()
        self.assertContains(page,'Пользовательское имя')
        self.assertContains(page,'Региональный')
        self.assertNotContains(page,'name="new_0"')
        self.assertNotContains(page,'name="category_0"')
        self.assertNotContains(page,'title="Новый канал"')

    def test_existing_subscriber_name_can_be_used_for_new_channel(self):
        sub=Subscriber.objects.create(name='Имеющийся центр',category='federal')
        self.preview()
        token=self.client.session['stats_preview']['token']
        self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':sub.name,'category_0':'other'})
        self.assertEqual(Subscriber.objects.count(),1)
        self.assertEqual(Channel.objects.get().subscriber_id,sub.pk)
        sub.refresh_from_db()
        self.assertEqual(sub.category,'federal')

    def test_failed_save_preserves_entered_name_and_type(self):
        self.preview()
        token=self.client.session['stats_preview']['token']
        page=self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':'','category_0':'federal'})
        self.assertContains(page,'name="new_0" value=""')
        self.assertContains(page,'<option value="federal" selected>Федеральный</option>',html=True)
        self.assertEqual(Record.objects.count(),0)


class ChannelDirectoryTests(TestCase):
    def setUp(self):
        self.sub=Subscriber.objects.create(name='Северный центр',category='regional')
        self.channel=Channel.objects.create(kind='AFTN',route_address='ADDR0001',name='Главный канал',subscriber=self.sub)
        self.other=Channel.objects.create(kind='AMHS',route_address='ADDR0002',name='Другой канал',subscriber=self.sub)
        self.batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='directory.txt',source='')
        self.record=Record.objects.create(batch=self.batch,channel=self.channel,received=5,sent=9,user_received=7)
        self.url=f'/statistics/channel/{self.channel.pk}/assign/'

    def assign(self, **changes):
        data=dict(subscriber_name='Новый центр',category='federal',expected_subscriber=str(self.sub.pk))
        data.update(changes)
        return self.client.post(self.url,data)

    def test_directory_layout_and_no_standalone_creation(self):
        page=self.client.get('/statistics/directory/')
        self.assertContains(page,'<h1 class="stats-heading">Абоненты и каналы</h1>',html=True)
        self.assertContains(page,'title="Сортировать по каналу"')
        self.assertContains(page,'title="Сортировать по абоненту"')
        self.assertContains(page,'<th rowspan="2">Категория</th><th rowspan="2">Тип</th>',html=True)
        self.assertContains(page,'<input type="submit" value="Найти">',html=True)
        self.assertContains(page,'data-assign-url="'+self.url+'"')
        self.assertContains(page,'directory.js')
        self.assertContains(page,'subscriber-suggestions.js')
        self.assertNotContains(page,'Новый абонент')
        self.assertNotContains(page,'>Создать<')
        self.assertEqual(self.client.post('/statistics/directory/',{'name':'Не создавать','category':'other'}).status_code,405)
        self.assertFalse(Subscriber.objects.filter(name='Не создавать').exists())

    def test_search_subscriber_channel_name_address_case_insensitive(self):
        for query, ids in [('СЕВЕРНЫЙ',[self.channel.pk,self.other.pk]),('addr0001',[self.channel.pk]),('главный',[self.channel.pk]),('НЕ НАЙДЁТСЯ',[])]:
            page=self.client.get('/statistics/directory/',{'q':query})
            self.assertEqual([c.pk for c in page.context['channels']],ids)
            self.assertEqual(page.context['search'],query)

    def test_reassign_existing_preserves_category_kind_name_and_records(self):
        target=Subscriber.objects.create(name='Международный центр',category='international')
        result=self.assign(subscriber_name=target.name,category='international',kind='AMHS',name='Не менять')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['category'],'international')
        self.channel.refresh_from_db()
        self.other.refresh_from_db()
        self.record.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual((self.channel.subscriber_id,self.channel.kind,self.channel.name),(target.pk,'AFTN','Главный канал'))
        self.assertEqual(self.other.subscriber_id,self.sub.pk)
        self.assertEqual(target.category,'international')
        self.assertEqual((self.record.channel_id,self.record.received,self.record.user_received),(self.channel.pk,5,7))
        sections=self.client.get('/statistics/?month=2026-05').context['category_sections']
        self.assertEqual(sections[0]['category'],'international')
        self.assertEqual(sections[0]['totals']['received'],7)

    def test_new_subscriber_category_and_defaults(self):
        result=self.assign()
        self.assertEqual(result.status_code,200)
        created=Subscriber.objects.get(name='Новый центр')
        self.assertEqual(created.category,'federal')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.name,'Северный центр')
        self.assertEqual(self.sub.category,'regional')
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.subscriber_id,created.pk)
        self.assertEqual(self.client.post(f'/statistics/channel/{self.other.pk}/assign/',{'subscriber_name':'Без категории','expected_subscriber':str(self.sub.pk)}).status_code,200)
        self.assertEqual(Subscriber.objects.get(name='Без категории').category,'other')

    def test_validation_stale_assignment_and_deleted_channel(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
        for changes in [dict(subscriber_name=''),dict(subscriber_name='x'*201),dict(category='invalid'),dict(expected_subscriber='abc')]:
            self.assertEqual(self.assign(**changes).status_code,400)
        self.assertEqual(Subscriber.objects.count(),1)
        self.assertEqual(self.assign().status_code,200)
        self.assertEqual(self.assign(subscriber_name='Не создавать дубль').status_code,409)
        self.assertFalse(Subscriber.objects.filter(name='Не создавать дубль').exists())
        self.channel.delete()
        self.assertEqual(self.assign().status_code,404)

    def test_csrf_and_existing_category_can_be_updated(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True)
        data=dict(subscriber_name=self.sub.name,category='international',expected_subscriber=str(self.sub.pk))
        self.assertEqual(client.post(self.url,data).status_code,403)
        client.get('/statistics/directory/')
        token=client.cookies['csrftoken'].value
        result=client.post(self.url,data,HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code,200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.category,'international')


class UploadPreviewResetTests(TestCase):
    def preview(self):
        return self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('unsaved.txt',AFTN.encode('utf-8'))})

    def test_reopening_upload_discards_unsaved_preview(self):
        preview=self.preview()
        self.assertTrue(preview.context['payload'])
        self.assertContains(preview,'class="upload-preview upload-preview-aftn"')
        token=self.client.session['stats_preview']['token']
        self.client.get('/statistics/directory/')
        page=self.client.get('/statistics/upload/')
        self.assertIsNone(page.context['payload'])
        self.assertEqual(page.context['rows'],[])
        self.assertNotContains(page,'class="upload-preview upload-preview-aftn"')
        self.assertNotContains(page,'Сохранить статистику')
        self.assertNotIn('stats_preview',self.client.session)
        self.assertEqual(Record.objects.count(),0)
        stale=self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':'Не сохранять'})
        self.assertEqual(stale.status_code,400)
        self.assertEqual(Subscriber.objects.count(),0)

    def test_failed_save_keeps_preview_until_reopen(self):
        self.preview()
        token=self.client.session['stats_preview']['token']
        page=self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':''})
        self.assertTrue(page.context['error'])
        self.assertTrue(page.context['payload'])
        self.assertIn('stats_preview',self.client.session)
        self.assertContains(page,'class="upload-preview upload-preview-aftn"')
        page=self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':'Центр'})
        self.assertEqual(page.status_code,302)
        self.assertEqual(Record.objects.count(),1)
        self.assertNotIn('stats_preview',self.client.session)
        page=self.client.get('/statistics/upload/')
        self.assertIsNone(page.context['payload'])
        self.assertEqual(Record.objects.count(),1)


class SubscriberLifecycleTests(TestCase):
    def setUp(self):
        self.sub=Subscriber.objects.create(name='Исходный абонент',comment='Комментарий')
        self.channel=Channel.objects.create(kind='AFTN',route_address='LIFE0001',name='Канал',subscriber=self.sub)
        self.batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='lifecycle',source='')
        self.record=Record.objects.create(batch=self.batch,channel=self.channel,received=3,sent=4)

    def test_delete_last_channel_removes_subscriber_and_statistics(self):
        self.channel.delete()
        self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())
        self.assertEqual(Record.objects.count(),0)
        self.assertTrue(ImportBatch.objects.filter(pk=self.batch.pk).exists())

    def test_queryset_deletion_keeps_subscriber_until_last_channel(self):
        extra=Channel.objects.create(kind='AMHS',route_address='LIFE0002',name='Другой',subscriber=self.sub)
        Channel.objects.filter(pk=self.channel.pk).delete()
        self.assertTrue(Subscriber.objects.filter(pk=self.sub.pk).exists())
        Channel.objects.filter(pk=extra.pk).delete()
        self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())

    def test_reassignment_through_model_form_cleans_old_subscriber(self):
        from .forms import ChannelForm
        target=Subscriber.objects.create(name='Целевой',category='federal')
        form=ChannelForm({'name':self.channel.name,'subscriber':target.pk},instance=self.channel)
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())
        self.assertEqual(Channel.objects.get(pk=self.channel.pk).subscriber_id,target.pk)
        self.assertTrue(Record.objects.filter(pk=self.record.pk).exists())

    def test_reassignment_endpoint_removes_only_empty_previous_subscriber(self):
        url=f'/statistics/channel/{self.channel.pk}/assign/'
        response=self.client.post(url,{'subscriber_name':'Новый','category':'regional','expected_subscriber':self.sub.pk})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())
        self.assertEqual(Subscriber.objects.get(name='Новый').category,'regional')
        self.assertTrue(Record.objects.filter(pk=self.record.pk).exists())

    def test_delete_and_reassignment_cleanup_roll_back_atomically(self):
        from django.db import transaction
        channel_pk=self.channel.pk
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.channel.delete()
                self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())
                raise RuntimeError('Откат удаления')
        self.assertTrue(Channel.objects.filter(pk=channel_pk).exists())
        self.assertTrue(Subscriber.objects.filter(pk=self.sub.pk).exists())
        self.assertTrue(Record.objects.filter(pk=self.record.pk).exists())
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                channel=Channel.objects.get(pk=channel_pk)
                channel.subscriber=Subscriber.objects.create(name='Временный')
                channel.save(update_fields=['subscriber'])
                self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())
                raise RuntimeError('Откат привязки')
        self.assertTrue(Subscriber.objects.filter(pk=self.sub.pk).exists())
        self.assertFalse(Subscriber.objects.filter(name='Временный').exists())
        self.assertEqual(Channel.objects.get(pk=channel_pk).subscriber_id,self.sub.pk)

    def test_admin_creation_disabled_and_channel_confirmation_lists_subscriber(self):
        from django.contrib.auth import get_user_model
        user=get_user_model().objects.create_superuser(username='lifecycle-admin',password='test')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/traffic_stats/subscriber/add/').status_code,403)
        self.assertEqual(self.client.post('/admin/traffic_stats/subscriber/add/',{'name':'Не создавать','category':'other'}).status_code,403)
        page=self.client.get(f'/admin/traffic_stats/channel/{self.channel.pk}/delete/')
        self.assertContains(page,'Исходный абонент (последний канал)')
        self.assertTrue(Subscriber.objects.filter(pk=self.sub.pk).exists())
        self.assertEqual(self.client.post(f'/admin/traffic_stats/channel/{self.channel.pk}/delete/',{'post':'yes'}).status_code,302)
        self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())

    def test_admin_bulk_deleting_all_channels_cleans_subscriber(self):
        from django.contrib.auth import get_user_model
        user=get_user_model().objects.create_superuser(username='bulk-lifecycle',password='test')
        self.client.force_login(user)
        extra=Channel.objects.create(kind='AMHS',route_address='BULK0002',name='Второй',subscriber=self.sub)
        data={'action':'delete_selected','_selected_action':[str(self.channel.pk),str(extra.pk)]}
        page=self.client.post('/admin/traffic_stats/channel/',data)
        self.assertContains(page,'Исходный абонент (последний канал)')
        data['post']='yes'
        self.assertEqual(self.client.post('/admin/traffic_stats/channel/',data).status_code,302)
        self.assertFalse(Subscriber.objects.filter(pk=self.sub.pk).exists())

    def test_subscriber_with_channel_but_without_statistics_is_kept(self):
        self.batch.delete()
        self.assertTrue(Channel.objects.filter(pk=self.channel.pk).exists())
        self.assertTrue(Subscriber.objects.filter(pk=self.sub.pk).exists())


class EmptySubscriberMigrationTests(TransactionTestCase):
    def test_cleanup_preserves_channels_records_and_attached_subscribers(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        old=('traffic_stats','0010_record_channel_cascade')
        new=('traffic_stats','0011_remove_empty_subscribers')
        executor=MigrationExecutor(connection)
        executor.migrate([old])
        try:
            apps=executor.loader.project_state([old]).apps
            Sub=apps.get_model('traffic_stats','Subscriber')
            Chan=apps.get_model('traffic_stats','Channel')
            empty=Sub.objects.create(name='Удалить пустую карточку',comment='В резервной копии')
            attached=Sub.objects.create(name='Оставить с каналом')
            channel=Chan.objects.create(kind='AFTN',route_address='MIGR0011',name='Без статистики',subscriber=attached)
            executor=MigrationExecutor(connection)
            executor.migrate([new])
            apps=executor.loader.project_state([new]).apps
            Sub=apps.get_model('traffic_stats','Subscriber')
            self.assertFalse(Sub.objects.filter(pk=empty.pk).exists())
            self.assertTrue(Sub.objects.filter(pk=attached.pk).exists())
            self.assertTrue(apps.get_model('traffic_stats','Channel').objects.filter(pk=channel.pk).exists())
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())


class DirectorySortingTests(TestCase):
    def setUp(self):
        beta=Subscriber.objects.create(name='Бета центр')
        alpha=Subscriber.objects.create(name='альфа центр')
        self.first=Channel.objects.create(kind='AFTN',route_address='AAA00001',name='Альфа канал',subscriber=beta)
        self.second=Channel.objects.create(kind='AMHS',route_address='ZZZ00001',name='Янки канал',subscriber=alpha)

    def test_both_columns_sort_in_both_directions(self):
        for column, direction, expected in [
            ('channel','asc',[self.first.pk,self.second.pk]),
            ('channel','desc',[self.second.pk,self.first.pk]),
            ('subscriber','asc',[self.second.pk,self.first.pk]),
            ('subscriber','desc',[self.first.pk,self.second.pk]),
        ]:
            page=self.client.get('/statistics/directory/',{'sort':column,'direction':direction})
            self.assertEqual([c.pk for c in page.context['channels']],expected)
            self.assertContains(page,'aria-sort="'+('ascending' if direction=='asc' else 'descending')+'"')

    def test_sort_links_and_search_preserve_each_other(self):
        from urllib.parse import parse_qs
        page=self.client.get('/statistics/directory/',{'q':'центр','sort':'subscriber','direction':'desc'})
        self.assertEqual(parse_qs(page.context['subscriber_sort_url'][1:]),{'q':['центр'],'sort':['subscriber'],'direction':['asc']})
        self.assertContains(page,'name="sort" value="subscriber"')
        self.assertContains(page,'name="direction" value="desc"')
        invalid=self.client.get('/statistics/directory/',{'sort':'bad','direction':'bad','q':'AAA'})
        self.assertEqual(invalid.context['sort'],'address')
        self.assertEqual(invalid.context['direction'],'asc')
        self.assertEqual([c.pk for c in invalid.context['channels']],[self.first.pk])


class PrintMenuTests(TestCase):
    def test_monthly_print_menu_and_no_print_actions_yet(self):
        sub=Subscriber.objects.create(name='Центр печати')
        channel=Channel.objects.create(kind='AFTN',route_address='PRINT001',name='Канал',subscriber=sub)
        batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='print.txt',source='')
        Record.objects.create(batch=batch,channel=channel,received=10,sent=20)
        page=self.client.get('/statistics/?month=2026-05')
        self.assertContains(page,'class="stats-print-menu"',count=1)
        self.assertContains(page,'traffic_stats/icons/printer.svg')
        self.assertContains(page,'class="stats-print-menu stats-download-menu"',count=1)
        self.assertContains(page,'traffic_stats/icons/box-arrow-down.svg')
        self.assertContains(page,'data-download-template="economists" href=')
        self.assertContains(page,'download=economists')
        self.assertContains(page,'data-download-template="all" href=')
        self.assertContains(page,'download=all')
        self.assertContains(page, 'class="stats-report-actions"')
        self.assertContains(page, '<summary class="button">', count=2)
        self.assertNotContains(page, 'Скачать Excel')
        self.assertNotContains(page, 'Скачать PDF')
        self.assertContains(page, 'data-print-template="centers" href=')
        self.assertContains(page, 'print=centers')
        self.assertContains(page, 'data-print-template="subscribers" href=')
        self.assertContains(page, 'print=subscribers')
        for key,label in [('channels','Каналы'),('all','Распечатать все')]:
            self.assertContains(page,f'data-print-template="{key}" href=')
            self.assertContains(page,f'print={key}')
        self.assertNotContains(self.client.get('/statistics/'),'class="stats-print-menu"')
        self.assertNotContains(self.client.get('/statistics/?month=2026-05&end_month=2026-06'),'class="stats-print-menu"')
        self.assertNotContains(self.client.get('/statistics/?month=2027-01'),'class="stats-print-menu"')

class MonthlyTemplateExportTests(TestCase):
    def setUp(self):
        self.month=date(2026,5,1)
        self.batches={kind:ImportBatch.objects.create(month=self.month,kind=kind,filename=kind,source='') for kind in ('AFTN','AMHS')}
        self.serial=0
        self.federal=Subscriber.objects.create(name='Федеральный А',category='federal')
        self.first=self.add(self.federal,'AFTN',10,20,number=97,override=0)
        self.add(self.federal,'AMHS',5,7)
        self.second=Subscriber.objects.create(name='Федеральный Б',category='federal')
        self.add(self.second,'AFTN',4,9,number=95)
        international=Subscriber.objects.create(name='Международный',category='international')
        self.add(international,'AMHS',11,12)
        regional=Subscriber.objects.create(name='Региональный',category='regional')
        self.add(regional,'AFTN',3,4,number=79)
        self.add(regional,'AMHS',7,8)
        local=Subscriber.objects.create(name='=Локальный',category='local')
        self.add(local,'AFTN',2,3,number=1)
        self.add(local,'AMHS',4,5)
        other=Subscriber.objects.create(name='Не включать прочее',category='other')
        self.add(other,'AFTN',100,200,number=9)
        later=ImportBatch.objects.create(month=date(2026,6,1),kind='AFTN',filename='later',source='')
        Record.objects.create(batch=later,channel=self.first,received=1000,sent=2000)

    def add(self, subscriber, kind, received, sent, number=None, override=None):
        self.serial+=1
        channel=Channel.objects.create(kind=kind,route_address=f'EXP{self.serial:05d}',name='Канал',subscriber=subscriber,logical_number=number)
        Record.objects.create(batch=self.batches[kind],channel=channel,received=received,sent=sent,user_received=override)
        return channel

    def export(self, query='month=2026-05'):
        from openpyxl import load_workbook
        response=self.client.get('/statistics/?'+query+'&download=all')
        self.assertEqual(response.status_code,200)
        return response, load_workbook(BytesIO(response.content))

    def test_requested_sheets_categories_summary_rows_and_period(self):
        response, book=self.export()
        self.assertEqual(book.sheetnames,['для согласования','Каналы ПД','ФГУП ГК','Сторонние','для Оператора'])
        from urllib.parse import unquote
        self.assertEqual(unquote(response['Content-Disposition'].split("''",1)[1]),'Статистика_май_2026.xlsx')
        agreement=book['для согласования']
        self.assertEqual((agreement['A12'].value,agreement['C12'].value),('Федеральный А',5))
        self.assertEqual((agreement['A13'].value,agreement['C13'].value),('Федеральный Б',4))
        self.assertIsNone(agreement['A14'].value)
        self.assertEqual(agreement['A7'].value,'ИТОГ РАБОТЫ ЗА май 2026')
        channels=book['Каналы ПД']
        self.assertEqual((channels['B7'].value,channels['D7'].value,channels['E7'].value),('Федеральный А',5,27))
        self.assertEqual(channels['F7'].value,'EXP00001, EXP00002')
        self.assertEqual(channels['D9'].value,'=SUM(D7:D8)')
        self.assertEqual(channels['B12'].value,'Международные')
        self.assertEqual((channels['B13'].value,channels['D13'].value),('Международный',11))
        regional=book['ФГУП ГК']
        self.assertEqual((regional['B7'].value,regional['D7'].value,regional['E7'].value),('Региональный',10,12))
        self.assertEqual(sum(cell.value=='Центры' for row in regional for cell in row),1)
        external=book['Сторонние']
        self.assertEqual(external.max_column,6)
        self.assertEqual([external.cell(6,column).value for column in (2,4,5,6)],['Абонент','Принято','Передано','Адрес'])
        self.assertEqual((external['B7'].value,external['D7'].value,external['E7'].value),('=Локальный',6,8))
        self.assertEqual(external['B7'].data_type,'s')
        operator_row = template_marker_row('для Оператора', '#абонент')
        for column in (1, 3, 4):
            self.assertIsNone(book['для Оператора'].cell(operator_row, column).value)
        for ws in book:
            for row in ws:
                for cell in row:
                    self.assertNotEqual(cell.value,'Не включать прочее')
                    if cell.data_type=='f':
                        self.assertNotIn('!',cell.value)
                        self.assertTrue(cell.value.startswith('=SUM(') or cell.value in ('=0','=TODAY()'))
                    if isinstance(cell.value,str):
                        self.assertNotIn('октябрь',cell.value.lower())

    def test_empty_sections_have_no_old_rows_and_zero_totals(self):
        _, book=self.export('month=2026-07')
        self.assertIsNone(book['для согласования']['A12'].value)
        self.assertIsNone(book['Каналы ПД']['B7'].value)
        self.assertEqual(book['Каналы ПД']['D8'].value,'=SUM(D7:D7)')
        self.assertIsNone(book['ФГУП ГК']['A6'].value)
        self.assertEqual(book['ФГУП ГК']['D8'].value,'=SUM(D7:D7)')
        self.assertIsNone(book['Сторонние']['A6'].value)
        self.assertEqual(book['Сторонние']['D8'].value,'=SUM(D7:D7)')

    def test_long_names_and_more_rows_than_template(self):
        for i in range(25):
            sub=Subscriber.objects.create(name=f'Длинное название федерального абонента {i:02d} '+('название '*8),category='federal')
            self.add(sub,'AFTN',i,i+1,number=i+100)
        _, book=self.export()
        sheet=book['Каналы ПД']
        self.assertEqual(sum(cell.value=='Международные' for row in sheet for cell in row),1)
        total_row=6+27+1
        self.assertEqual(sheet.cell(total_row,4).value,'=SUM(D7:D33)')
        self.assertGreater(sheet.row_dimensions[7].height,15)
        self.assertTrue(sheet['B7'].alignment.wrap_text)
        self.assertEqual(book['для согласования']['A38'].value,'Федеральный Б')

    def test_economists_workbook_matches_three_sheets_of_full_export(self):
        from openpyxl import load_workbook
        from urllib.parse import unquote
        _, full = self.export()
        response = self.client.get('/statistics/?month=2026-05&download=economists')
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(book.sheetnames, ['Каналы ПД', 'ФГУП ГК', 'Сторонние'])
        self.assertEqual(unquote(response['Content-Disposition'].split("''", 1)[1]), 'Статистика_май_2026_для_экономистов.xlsx')
        for sheet in book:
            source = full[sheet.title]
            self.assertEqual([[c.value for c in row] for row in sheet], [[c.value for c in row] for row in source])
            self.assertEqual(str(sheet.merged_cells), str(source.merged_cells))
            self.assertEqual(sheet.print_area, source.print_area)
            for row in sheet:
                for cell in row:
                    self.assertEqual(copy(cell.font), copy(source[cell.coordinate].font))
                    self.assertEqual(copy(cell.fill), copy(source[cell.coordinate].fill))
            self.assertEqual({i: d.height for i, d in sheet.row_dimensions.items()}, {i: d.height for i, d in source.row_dimensions.items()})

    def test_centers_print_uses_only_agreement_sheet_and_effective_counts(self):
        page = self.client.get('/statistics/?month=2026-05&print=centers')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Для согласования с центрами')
        self.assertContains(page, 'Федеральный А')
        self.assertContains(page, 'Федеральный Б')
        self.assertContains(page, 'ИТОГ РАБОТЫ ЗА май 2026')
        self.assertContains(page, 'traffic_stats/js/print-sheet.js')
        self.assertNotContains(page, 'Международный')
        self.assertNotContains(page, '=Локальный')
        self.assertNotContains(page, 'Не включать прочее')
        _, book = self.export()
        expected = book['для согласования']
        self.assertEqual(page.context['rows'][11]['cells'][1]['value'], str(expected['C12'].value))
        self.assertEqual(page.context['rows'][12]['cells'][1]['value'], str(expected['C13'].value))
        self.assertNotContains(page, '#федеральный')
        self.assertNotContains(page, 'stats-report-heading')
        self.assertIn('pt', page.context['margins'])

    def test_centers_print_requires_single_month_and_keeps_filters(self):
        for query in ('print=centers', 'month=2026-05&end_month=2026-06&print=centers'):
            self.assertEqual(self.client.get('/statistics/?' + query).status_code, 400)
        page = self.client.get(f'/statistics/?month=2026-05&print=centers&subscriber={self.federal.pk}')
        self.assertContains(page, 'Федеральный А')
        self.assertNotContains(page, 'Федеральный Б')

    def test_centers_print_escapes_subscriber_text(self):
        self.federal.name = '<script>alert(1)</script>'
        self.federal.save()
        page = self.client.get('/statistics/?month=2026-05&print=centers')
        self.assertContains(page, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(page, '<script>alert(1)</script>')

    def test_short_rows_keep_template_height_in_downloads_and_print(self):
        from openpyxl import load_workbook
        from .monthly_export import TEMPLATE
        source = load_workbook(TEMPLATE)
        try:
            expected = source['Каналы ПД'].row_dimensions[7].height
            agreement_height = source['для согласования'].row_dimensions[12].height
        finally:
            source.close()
        _, full = self.export()
        self.assertEqual(full['Каналы ПД']['B8'].value, 'Федеральный Б')
        self.assertEqual(full['Каналы ПД'].row_dimensions[8].height, expected)
        response = self.client.get('/statistics/?month=2026-05&download=economists')
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(book['Каналы ПД'].row_dimensions[8].height, expected)
        page = self.client.get('/statistics/?month=2026-05&print=centers')
        self.assertEqual(page.context['rows'][12]['height'], agreement_height)

    def test_channels_and_all_print_correct_sheets_in_order(self):
        for variant, expected in (
            ('channels', ['Каналы ПД', 'ФГУП ГК', 'Сторонние']),
            ('all', ['для согласования', 'Каналы ПД', 'ФГУП ГК', 'Сторонние', 'для Оператора']),
        ):
            page = self.client.get(f'/statistics/?month=2026-05&print={variant}')
            self.assertEqual(page.status_code, 200)
            sheets = page.context['sheets']
            self.assertEqual([sheet['sheet_label'] for sheet in sheets], expected)
            self.assertContains(page, '<main class="print-sheet"', count=len(expected))
            self.assertContains(page, 'traffic_stats/js/print-sheet.js', count=1)
            self.assertContains(page, 'break-before: page')
            self.assertNotContains(page, '=SUM(')
            self.assertNotContains(page, '=TODAY(')
            # Все листы сохраняют компактные верхнее/нижнее поля и свои боковые.
            self.assertTrue(all(sheet['margins'].split()[::2] == ['10mm', '10mm'] for sheet in sheets))
            channels = next(sheet for sheet in sheets if sheet['sheet_label']=='Каналы ПД')
            values = [cell['value'] for row in channels['rows'] for cell in row['cells']]
            self.assertIn('9', values)  # федеральные: 5 + 4 с учётом корректировки
            self.assertIn('36', values)  # передано: 20 + 7 + 9
            from datetime import datetime
            from django.utils import timezone
            self.assertIn(datetime.now(timezone.get_current_timezone()).strftime('%d.%m.%Y'), values)

    def test_period_buttons_use_filtered_range_totals(self):
        from openpyxl import load_workbook

        params = {'month': '2026-05', 'end_month': '2026-06', 'subscriber': self.federal.pk}
        page = self.client.get('/statistics/', params)
        self.assertContains(page, 'class="button stats-period-action"', count=2)
        self.assertContains(page, f'subscriber={self.federal.pk}&amp;print=period')
        self.assertContains(page, f'subscriber={self.federal.pk}&amp;export=xlsx')
        response = self.client.get('/statistics/', dict(params, export='xlsx'))
        self.assertIn('statistics-2026-05-to-2026-06.xlsx', response['Content-Disposition'])
        with BytesIO(response.content) as output:
            book = load_workbook(output)
            try:
                rows = list(book.active.values)
                self.assertIn((self.federal.name, 1005, 2027, None), rows)
            finally:
                book.close()
        printed = self.client.get('/statistics/', dict(params, print='period'))
        self.assertTemplateUsed(printed, 'traffic_stats/print_period.html')
        self.assertContains(printed, 'Статистика по каналам за май 2026 — июнь 2026')
        self.assertContains(printed, self.federal.name)
        self.assertNotContains(printed, 'Международный')
        self.assertNotContains(printed, 'stat-chart-button')
        self.assertEqual(printed.context['category_sections'][0]['totals'], {'received': 1005, 'sent': 2027})
        self.assertEqual(self.client.get('/statistics/?month=2026-05&print=period').status_code, 400)

    def test_multi_sheet_print_requires_month_and_retains_filter(self):
        for variant in ('channels', 'all'):
            for query in ('', 'month=2026-05&end_month=2026-06&'):
                self.assertEqual(self.client.get(f'/statistics/?{query}print={variant}').status_code, 400)
            page = self.client.get(f'/statistics/?month=2026-05&print={variant}&subscriber={self.federal.pk}')
            self.assertContains(page, 'Федеральный А')
            self.assertNotContains(page, 'Федеральный Б')

    def test_single_month_required_and_menu_link_enabled(self):
        for query in ('download=all','month=2026-05&end_month=2026-06&download=all', 'download=economists', 'month=2026-05&end_month=2026-06&download=economists'):
            self.assertEqual(self.client.get('/statistics/?'+query).status_code,400)
        page=self.client.get('/statistics/?month=2026-05')
        self.assertContains(page,'data-download-template="all" href=')
        self.assertContains(page,'data-download-template="economists" href=')

class ChannelMailingTests(TestCase):
    def setUp(self):
        self.sub=Subscriber.objects.create(name='Абонент рассылки',category='regional')
        self.channel=Channel.objects.create(kind='AFTN',name='Название канала',route_address='MAIL0001',subscriber=self.sub)
        self.other=Channel.objects.create(kind='AMHS',name='Второй канал',route_address='MAIL0002',subscriber=self.sub)
        batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='mail',source='')
        self.record=Record.objects.create(batch=batch,channel=self.channel,received=10,sent=20)
        self.url=f'/statistics/channel/{self.channel.pk}/assign/'

    def post(self, **changes):
        values=dict(subscriber_name=self.sub.name,expected_subscriber=str(self.sub.pk),category='regional')
        values.update(changes)
        return self.client.post(self.url,values)

    def state(self):
        from .views import _channel_edit_state
        self.channel.refresh_from_db()
        return _channel_edit_state(self.channel)

    def test_defaults_and_independent_mailing_addresses(self):
        self.assertEqual(self.channel.mailing_addresses,'MAIL0001')
        self.assertFalse(self.channel.mailing_received)
        self.assertFalse(self.channel.mailing_sent)
        self.channel.route_address='CHANGED1'
        self.channel.save(update_fields=['route_address'])
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.mailing_addresses,'MAIL0001')
        self.channel.mailing_addresses=''
        self.channel.save(update_fields=['mailing_addresses'])
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.mailing_addresses,'')
        explicit=Channel.objects.create(kind='AMHS',name='Явный',route_address='EXPLICIT',subscriber=self.sub,mailing_addresses='FIRST, SECOND')
        self.assertEqual(explicit.mailing_addresses,'FIRST, SECOND')

    def test_edit_address_flags_addresses_and_shared_subscriber_category(self):
        import json
        before=json.dumps(self.state())
        response=self.post(route_address='EDIT0001',mailing_received='1',mailing_sent='0',mailing_addresses='FIRST001\nSECOND02',category='federal',expected_state=before,kind='AMHS')
        self.assertEqual(response.status_code,200)
        self.channel.refresh_from_db()
        self.other.refresh_from_db()
        self.sub.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.channel.route_address,'EDIT0001')
        self.assertTrue(self.channel.mailing_received)
        self.assertFalse(self.channel.mailing_sent)
        self.assertEqual(self.channel.mailing_addresses,'FIRST001\nSECOND02')
        self.assertEqual(self.channel.kind,'AFTN')
        self.assertEqual(self.other.subscriber.category,'federal')
        self.assertEqual(self.record.channel_id,self.channel.pk)
        self.assertEqual((self.record.received,self.record.sent),(10,20))
        page=self.client.get('/statistics/directory/')
        self.assertContains(page,'title="Сортировать по адресу"')
        self.assertContains(page,'<th colspan="2">Рассылка</th>',html=True)
        self.assertContains(page,'<th>ПРМ</th><th>ПРД</th>',html=True)
        self.assertContains(page,'<th rowspan="2">Адрес рассылки</th>',html=True)
        self.assertContains(page,'Название канала')
        self.assertContains(page,'EDIT0001')
        self.assertContains(page,'data-edit-existing-category')

    def test_duplicate_address_invalid_flags_and_category_are_atomic(self):
        Channel.objects.create(kind='AFTN',name='Занятый',route_address='TAKEN001',subscriber=self.sub)
        response=self.post(subscriber_name='Не создавать',route_address='TAKEN001',category='international')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Subscriber.objects.filter(name='Не создавать').exists())
        for changes in [dict(route_address=''),dict(route_address='x'*201),dict(mailing_received='bad'),dict(category='bad'),dict(expected_state='bad JSON')]:
            self.assertEqual(self.post(**changes).status_code,400)
        self.channel.refresh_from_db()
        self.sub.refresh_from_db()
        self.assertEqual(self.channel.route_address,'MAIL0001')
        self.assertEqual(self.sub.category,'regional')
        self.assertFalse(self.channel.mailing_received)

    def test_same_address_in_another_type_allowed_and_unchecked_flags_saved(self):
        self.assertEqual(self.post(route_address=self.other.route_address,mailing_received='1',mailing_sent='1').status_code,200)
        self.assertEqual(self.post(mailing_received='0',mailing_sent='0',mailing_addresses='').status_code,200)
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.mailing_received)
        self.assertFalse(self.channel.mailing_sent)
        self.assertEqual(self.channel.mailing_addresses,'')

    def test_stale_channel_or_category_does_not_overwrite_changes(self):
        import json
        state=json.dumps(self.state())
        self.channel.mailing_received=True
        self.channel.save(update_fields=['mailing_received'])
        self.assertEqual(self.post(expected_state=state,mailing_received='0',subscriber_name='Не создавать').status_code,409)
        self.assertFalse(Subscriber.objects.filter(name='Не создавать').exists())
        state=json.dumps(self.state())
        self.sub.category='international'
        self.sub.save(update_fields=['category'])
        self.assertEqual(self.post(expected_state=state,category='other').status_code,409)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.category,'international')


class ChannelMailingMigrationTests(TransactionTestCase):
    def test_existing_channels_get_address_as_default_mailing_address(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        old=('traffic_stats','0011_remove_empty_subscribers')
        new=('traffic_stats','0012_channel_mailing')
        executor=MigrationExecutor(connection)
        executor.migrate([old])
        try:
            apps=executor.loader.project_state([old]).apps
            sub=apps.get_model('traffic_stats','Subscriber').objects.create(name='Перенос рассылки')
            channel=apps.get_model('traffic_stats','Channel').objects.create(kind='AFTN',name='Имя',route_address='MIGR0012',subscriber=sub)
            executor=MigrationExecutor(connection)
            executor.migrate([new])
            apps=executor.loader.project_state([new]).apps
            saved=apps.get_model('traffic_stats','Channel').objects.get(pk=channel.pk)
            self.assertEqual(saved.mailing_addresses,'MIGR0012')
            self.assertFalse(saved.mailing_received)
            self.assertFalse(saved.mailing_sent)
            self.assertEqual((saved.name,saved.subscriber_id),('Имя',sub.pk))
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

class DirectoryAddressLayoutTests(TestCase):
    def setUp(self):
        self.sub=Subscriber.objects.create(name='Абонент полей',category='regional')
        self.first=Channel.objects.create(kind='AFTN',name='Янтарь',route_address='AAA00001',subscriber=self.sub)
        self.second=Channel.objects.create(kind='AMHS',name='Альфа',route_address='ZZZ00001',subscriber=self.sub)

    def test_address_is_first_and_sorts_independently_from_channel_name(self):
        for column,direction,expected in [('address','asc',[self.first.pk,self.second.pk]),('address','desc',[self.second.pk,self.first.pk]),('channel','asc',[self.second.pk,self.first.pk])]:
            page=self.client.get('/statistics/directory/',{'sort':column,'direction':direction})
            self.assertEqual([c.pk for c in page.context['channels']],expected)
        page=self.client.get('/statistics/directory/')
        self.assertEqual(page.context['sort'],'address')
        html=page.content.decode()
        self.assertLess(html.index('title="Сортировать по адресу"'),html.index('title="Сортировать по каналу"'))
        self.assertLess(html.index('class="directory-address-value"'),html.index('class="directory-channel-name"'))
        self.assertContains(page,'type="text" data-channel-field="mailing_addresses" maxlength="200"')
        self.assertNotContains(page,'<textarea')

    def test_mailing_address_length_checked_on_server_without_truncation(self):
        url=f'/statistics/channel/{self.first.pk}/assign/'
        data=dict(subscriber_name=self.sub.name,expected_subscriber=str(self.sub.pk),category='regional',mailing_addresses='A'*200)
        self.assertEqual(self.client.post(url,data).status_code,200)
        self.first.refresh_from_db()
        self.assertEqual(self.first.mailing_addresses,'A'*200)
        data.update(mailing_addresses='B'*201,subscriber_name='Не создавать',category='federal')
        self.assertEqual(self.client.post(url,data).status_code,400)
        self.first.refresh_from_db()
        self.assertEqual(self.first.mailing_addresses,'A'*200)
        self.assertFalse(Subscriber.objects.filter(name='Не создавать').exists())

class UploadAddressAndMailingTests(TestCase):
    def preview(self, text=AMHS):
        return self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('channels.txt',text.encode('utf-8'))})

    def save(self, **changes):
        values=dict(action='save',token=self.client.session['stats_preview']['token'])
        values.update(changes)
        return self.client.post('/statistics/upload/',values)

    def test_new_amhs_address_and_local_mailing_defaults_and_reimport(self):
        page=self.preview()
        self.assertContains(page,'<th class="route-address">Адрес</th><th>Канал</th>',html=True)
        self.assertContains(page,'name="route_address_0" value=""')
        self.assertContains(page,'<td class="upload-channel-name">MTA-UHPP-1</td>',html=True)
        page=self.save(new_0='Локальный центр',category_0='local',route_address_0='УХППЫФЫЬ')
        self.assertEqual(page.status_code,302)
        channel=Channel.objects.get()
        self.assertEqual(channel.name,'MTA-UHPP-1')
        self.assertEqual(channel.route_address,'УХППЫФЫЬ')
        self.assertTrue(channel.mailing_received)
        self.assertFalse(channel.mailing_sent)
        self.assertEqual(channel.mailing_addresses,'УХППЫФЫЬ')
        channel.mailing_received=False
        channel.mailing_sent=True
        channel.mailing_addresses='CUSTOM01'
        channel.save(update_fields=['mailing_received','mailing_sent','mailing_addresses'])
        page=self.preview(AMHS.replace(';108;2',';109;3'))
        self.assertEqual(page.context['rows'][0]['channel'].pk,channel.pk)
        self.assertContains(page,'УХППЫФЫЬ')
        self.assertNotContains(page,'name="route_address_0"')
        self.assertNotContains(page,'title="Новый канал"')
        self.assertEqual(self.save(replace='yes',route_address_0='IGNORED').status_code,302)
        channel.refresh_from_db()
        self.assertEqual(Channel.objects.count(),1)
        self.assertEqual(channel.route_address,'УХППЫФЫЬ')
        self.assertFalse(channel.mailing_received)
        self.assertTrue(channel.mailing_sent)
        self.assertEqual(channel.mailing_addresses,'CUSTOM01')
        self.assertEqual(Record.objects.get().received,109)

    def test_aftn_address_not_editable_and_existing_channel_name_displayed(self):
        page=self.preview(AFTN)
        self.assertNotContains(page,'name="route_address_0"')
        self.assertEqual(self.save(new_0='Локальный',category_0='local',route_address_0='IGNORED').status_code,302)
        channel=Channel.objects.get()
        self.assertEqual(channel.route_address,'УЛЛЛЫФЫА')
        self.assertEqual(channel.mailing_addresses,'УЛЛЛЫФЫА')
        self.assertTrue(channel.mailing_received)
        channel.name='Сохранённое имя'
        channel.save(update_fields=['name'])
        page=self.preview(AFTN)
        self.assertContains(page,'<td class="upload-channel-name">Сохранённое имя</td>',html=True)
        self.assertNotContains(page,'name="route_address_0"')

    def test_new_nonlocal_stays_unchecked_and_existing_local_category_used(self):
        self.preview()
        self.assertEqual(self.save(new_0='Региональный',category_0='regional').status_code,302)
        channel=Channel.objects.get()
        self.assertFalse(channel.mailing_received)
        self.assertEqual(channel.mailing_addresses,'')
        sub=Subscriber.objects.create(name='Имеющийся локальный',category='local')
        self.preview(AMHS.replace('MTA-UHPP-1','MTA-OTHER-1'))
        self.assertEqual(self.save(new_0=sub.name,category_0='other',route_address_0='LOCAL001',replace='yes').status_code,302)
        new=Channel.objects.get(route_address='LOCAL001')
        self.assertEqual(new.subscriber_id,sub.pk)
        self.assertTrue(new.mailing_received)

    def test_invalid_and_duplicate_amhs_addresses_keep_preview_without_partial_save(self):
        self.preview()
        for address in ('x'*201,):
            page=self.save(new_0='Не создавать',category_0='local',route_address_0=address)
            self.assertEqual(page.status_code,200)
            self.assertTrue(page.context['error'])
            self.assertEqual(Channel.objects.count(),0)
            self.assertEqual(Subscriber.objects.count(),0)
        self.preview(AMHS+'\nMTA-SECOND-1;5;6')
        page=self.save(new_0='Первый',new_1='Второй',category_0='local',category_1='local',route_address_0='SAME0001',route_address_1='SAME0001')
        self.assertTrue(page.context['error'])
        self.assertContains(page,'name="route_address_0" value="SAME0001"')
        self.assertContains(page,'name="route_address_1" value="SAME0001"')
        self.assertEqual(Channel.objects.count(),0)
        self.assertEqual(Record.objects.count(),0)
        self.assertEqual(Subscriber.objects.count(),0)

    def test_existing_address_collision_does_not_create_or_reassign_channel(self):
        sub=Subscriber.objects.create(name='Существующий')
        old=Channel.objects.create(kind='AMHS',route_address='EXIST001',name='Другой источник',subscriber=sub)
        self.preview()
        page=self.save(new_0='Не создавать',route_address_0='EXIST001')
        self.assertTrue(page.context['error'])
        self.assertEqual(Channel.objects.count(),1)
        self.assertFalse(Subscriber.objects.filter(name='Не создавать').exists())
        self.assertEqual(Channel.objects.get(pk=old.pk).subscriber_id,sub.pk)

    def test_ambiguous_amhs_names_are_not_matched_arbitrarily(self):
        sub=Subscriber.objects.create(name='Абонент')
        for address in ('AMBIG001','AMBIG002'):
            Channel.objects.create(kind='AMHS',route_address=address,name='MTA-UHPP-1',subscriber=sub)
        page=self.preview()
        self.assertIsNone(page.context['rows'][0]['channel'])
        self.assertContains(page,'name="route_address_0"')

    def test_source_name_matching_another_address_does_not_merge_channels(self):
        sub=Subscriber.objects.create(name='Абонент')
        channel=Channel.objects.create(kind='AMHS',route_address='ALIAS001',name='MTA-UHPP-1',subscriber=sub)
        self.preview(AMHS+'\nALIAS001;5;6')
        page=self.save(new_1='Другой абонент')
        self.assertEqual(page.status_code,302)
        self.assertEqual(Record.objects.count(),2)
        self.assertEqual(Channel.objects.count(),2)
        new=Channel.objects.get(name='ALIAS001')
        self.assertEqual(new.route_address,'')
        self.assertNotEqual(new.pk,channel.pk)

class AmhsOptionalAddressTests(TestCase):
    def preview(self,text=AMHS):
        return self.client.post('/statistics/upload/',{'action':'preview','file':SimpleUploadedFile('amhs.txt',text.encode('utf-8'))})

    def test_multiple_new_amhs_channels_with_blank_addresses_and_reimport(self):
        text=AMHS+'\nMTA-SECOND-1;5;6'
        page=self.preview(text)
        self.assertContains(page,'name="route_address_0" value=""')
        self.assertContains(page,'name="route_address_1" value=""')
        self.assertNotContains(page,'maxlength="200" required aria-label="Адрес нового AMHS')
        token=self.client.session['stats_preview']['token']
        result=self.client.post('/statistics/upload/',{'action':'save','token':token,'new_0':'Локальный','category_0':'local','new_1':'Другой','category_1':'regional'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(Channel.objects.filter(kind='AMHS',route_address='').count(),2)
        local=Channel.objects.get(name='MTA-UHPP-1')
        self.assertTrue(local.mailing_received)
        self.assertEqual(local.mailing_addresses,'')
        self.assertEqual(Record.objects.get(channel=local).received,108)
        page=self.preview(text)
        self.assertTrue(all(row['channel'] for row in page.context['rows']))
        self.assertNotContains(page,'name="route_address_0"')
        token=self.client.session['stats_preview']['token']
        self.assertEqual(self.client.post('/statistics/upload/',{'action':'save','token':token,'replace':'yes'}).status_code,302)
        self.assertEqual(Channel.objects.count(),2)
        self.assertEqual(Record.objects.count(),2)

    def test_amhs_lookup_uses_name_even_when_other_channel_address_matches(self):
        sub=Subscriber.objects.create(name='Старый абонент')
        wrong=Channel.objects.create(kind='AMHS',name='Другой канал',route_address='MTA-UHPP-1',subscriber=sub)
        correct=Channel.objects.create(kind='AMHS',name='MTA-UHPP-1',route_address='REAL0001',subscriber=sub)
        page=self.preview()
        self.assertEqual(page.context['rows'][0]['channel'].pk,correct.pk)
        token=self.client.session['stats_preview']['token']
        self.assertEqual(self.client.post('/statistics/upload/',{'action':'save','token':token}).status_code,302)
        self.assertTrue(Record.objects.filter(channel=correct).exists())
        self.assertFalse(Record.objects.filter(channel=wrong).exists())
        self.assertEqual(Channel.objects.get(pk=correct.pk).route_address,'REAL0001')

    def test_directory_allows_clearing_amhs_but_not_aftn_address(self):
        sub=Subscriber.objects.create(name='Абонент')
        amhs=Channel.objects.create(kind='AMHS',name='AMHS',route_address='OLD00001',subscriber=sub)
        aftn=Channel.objects.create(kind='AFTN',name='AFTN',route_address='AFTN0001',subscriber=sub)
        data={'subscriber_name':sub.name,'expected_subscriber':str(sub.pk),'route_address':''}
        self.assertEqual(self.client.post(f'/statistics/channel/{amhs.pk}/assign/',data).status_code,200)
        self.assertEqual(Channel.objects.get(pk=amhs.pk).route_address,'')
        self.assertEqual(self.client.post(f'/statistics/channel/{aftn.pk}/assign/',data).status_code,400)

    def test_parser_separates_amhs_name_from_absent_address_and_model_validation(self):
        from django.core.exceptions import ValidationError
        from django.db import IntegrityError,transaction
        parsed=parse(AMHS)
        self.assertEqual(parsed['rows'][0]['source_name'],'MTA-UHPP-1')
        self.assertEqual(parsed['rows'][0]['route_address'],'')
        sub=Subscriber.objects.create(name='Абонент')
        first=Channel(kind='AMHS',name='Первый',subscriber=sub)
        first.full_clean()
        first.save()
        second=Channel(kind='AMHS',name='Второй',subscriber=sub)
        second.full_clean()
        second.save()
        self.assertEqual(Channel.objects.filter(route_address='').count(),2)
        with self.assertRaises(ValidationError):
            Channel(kind='AFTN',name='Пустой AFTN',subscriber=sub).full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Channel.objects.create(kind='AFTN',name='Пустой AFTN',subscriber=sub,route_address='')


class StatisticsChannelDisplayTests(TestCase):
    def test_amhs_uses_name_in_single_and_detail_rows_and_standard_exports(self):
        from openpyxl import load_workbook
        first=Subscriber.objects.create(name='Первый абонент',category='federal')
        second=Subscriber.objects.create(name='Второй абонент',category='federal')
        amhs_batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AMHS',filename='amhs',source='')
        aftn_batch=ImportBatch.objects.create(month=date(2026,5,1),kind='AFTN',filename='aftn',source='')
        single=Channel.objects.create(kind='AMHS',name='MTA-SINGLE',route_address='HIDE0001',subscriber=first)
        detail=Channel.objects.create(kind='AMHS',name='MTA-DETAIL',route_address='',subscriber=second)
        aftn=Channel.objects.create(kind='AFTN',name='Не показывать вместо адреса',route_address='AFTN0001',subscriber=second)
        Record.objects.create(batch=amhs_batch,channel=single,received=10,sent=20)
        Record.objects.create(batch=amhs_batch,channel=detail,received=3,sent=4)
        Record.objects.create(batch=aftn_batch,channel=aftn,received=5,sent=6)
        page=self.client.get('/statistics/?month=2026-05')
        self.assertContains(page,'<td class="route-address">MTA-SINGLE</td>',html=True)
        self.assertContains(page,'<td class="route-address">MTA-DETAIL</td>',html=True)
        self.assertContains(page,'<td class="route-address">AFTN0001</td>',html=True)
        self.assertNotContains(page,'HIDE0001')
        self.assertNotContains(page,'Не показывать вместо адреса')
        response=self.client.get('/statistics/?month=2026-05&export=xlsx')
        sheet=load_workbook(BytesIO(response.content)).active
        labels=[cell.value for cell in sheet['D'] if cell.value is not None]
        for label in ['MTA-SINGLE','MTA-DETAIL','AFTN0001']:
            self.assertIn(label,labels)
        self.assertNotIn('HIDE0001',labels)

class MarkerWorkbookExportTests(TestCase):
    def setUp(self):
        self.sub=Subscriber.objects.create(name='Общий абонент',category='federal')
        self.batches={kind:ImportBatch.objects.create(month=date(2026,5,1),kind=kind,filename=kind,source='') for kind in ('AFTN','AMHS')}
        self.serial=0
        self.add('ПРМ','РАМ',True,False,10,100,override_received=0,mail='ПОЛУЧАТЕЛЬ ПРМ')
        self.add('ПРД','',False,True,200,20,override_sent=0,mail='ПОЛУЧАТЕЛЬ ПРД',kind='AMHS')
        self.add('Оба','ЛХС',True,True,30,40,mail='ОБА001, ОБА002')
        self.add('Без флажков','НЕ ВЫВОДИТЬ',False,False,1000,2000,mail='НЕ ВЫВОДИТЬ')
        other=Subscriber.objects.create(name='Другой категории',category='other')
        self.add('Прочий','',True,False,5,6,subscriber=other,mail='ПРОЧИЙ001')

    def add(self,name,designation,received_flag,sent_flag,received,sent,subscriber=None,mail='',kind='AFTN',override_received=None,override_sent=None):
        self.serial+=1
        channel=Channel.objects.create(name=name,kind=kind,route_address=f'OPR{self.serial:05d}' if kind=='AFTN' else '',subscriber=subscriber or self.sub,
            transmission_designation=designation,mailing_received=received_flag,mailing_sent=sent_flag,mailing_addresses=mail)
        Record.objects.create(batch=self.batches[kind],channel=channel,received=received,sent=sent,user_received=override_received,user_sent=override_sent)
        return channel

    def export(self,query='month=2026-05'):
        from openpyxl import load_workbook
        response=self.client.get('/statistics/?'+query+'&download=all')
        self.assertEqual(response.status_code,200)
        return load_workbook(BytesIO(response.content))

    def test_operator_groups_subscriber_and_uses_only_enabled_directions(self):
        sheet=self.export()['для Оператора']
        start = template_marker_row('для Оператора', '#абонент')
        rows={sheet.cell(row,1).value:(sheet.cell(row,3).value,sheet.cell(row,4).value,sheet.cell(row,5).value) for row in range(start,start+2)}
        self.assertEqual(rows,{
            'Общий абонент':(30,40,'ОБА001, ОБА002, ПОЛУЧАТЕЛЬ ПРД, ПОЛУЧАТЕЛЬ ПРМ'),
            'Другой категории':(5,None,'ПРОЧИЙ001'),
        })
        self.assertEqual(sheet.cell(start+2,3).value,f'=SUM(C{start}:C{start+1})')
        self.assertEqual(sheet.cell(start+2,4).value,f'=SUM(D{start}:D{start+1})')
        self.assertIn(f'A{start+1}:B{start+1}',str(sheet.merged_cells))
        self.assertTrue(any(cell.value=='подпись оператора:  ____________' for row in sheet for cell in row))
        self.assertFalse(any(cell.value=='НЕ ВЫВОДИТЬ' for row in sheet for cell in row))

    def test_operator_print_matches_sheet_and_calculates_totals(self):
        page = self.client.get('/statistics/?month=2026-05&print=subscribers')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Для согласования с абонентами')
        self.assertNotContains(page, 'Для согласования с центрами')
        self.assertContains(page, 'traffic_stats/js/print-sheet.js')
        self.assertContains(page, 'ОБА001, ОБА002, ПОЛУЧАТЕЛЬ ПРД, ПОЛУЧАТЕЛЬ ПРМ')
        self.assertNotContains(page, 'НЕ ВЫВОДИТЬ')
        self.assertNotContains(page, 'Общий абонент /')
        rows = page.context['rows']
        subscriber_row = next(row for row in rows if row['cells'][0]['value']=='Общий абонент')
        self.assertEqual([cell['value'] for cell in subscriber_row['cells']][:3], ['Общий абонент', '30', '40'])
        total = next(row for row in rows if any(cell['value']=='Итого:' for cell in row['cells']))
        self.assertEqual([cell['value'] for cell in total['cells']][1:4], ['Итого:', '35', '40'])
        self.assertNotContains(page, '=SUM(')

    def test_operator_print_requires_single_month_and_keeps_subscriber_filter(self):
        for query in ('print=subscribers', 'month=2026-05&end_month=2026-06&print=subscribers'):
            self.assertEqual(self.client.get('/statistics/?'+query).status_code, 400)
        page = self.client.get(f'/statistics/?month=2026-05&print=subscribers&subscriber={self.sub.pk}')
        self.assertContains(page, 'Общий абонент')
        self.assertNotContains(page, 'Другой категории')
        total = next(row for row in page.context['rows'] if any(cell['value']=='Итого:' for cell in row['cells']))
        self.assertEqual([cell['value'] for cell in total['cells']][1:4], ['Итого:', '30', '40'])

    def test_empty_operator_print_has_zero_totals(self):
        page = self.client.get('/statistics/?month=2026-07&print=subscribers')
        self.assertEqual(page.status_code, 200)
        total = next(row for row in page.context['rows'] if any(cell['value']=='Итого:' for cell in row['cells']))
        self.assertEqual([cell['value'] for cell in total['cells']][1:4], ['Итого:', '0', '0'])

    def test_operator_deduplicates_addresses_from_selected_channels(self):
        self.add('Повтор адресов','ЛХС',True,False,7,900,
            mail='ОБА001; ОБА002, ОБА003\nОБА003')
        sheet=self.export()['для Оператора']
        row=next(row for row in sheet if row[0].value=='Общий абонент')
        self.assertEqual(row[2].value,37)
        self.assertEqual(row[3].value,40)
        self.assertEqual(row[4].value,'ОБА001, ОБА002, ОБА003, ПОЛУЧАТЕЛЬ ПРД, ПОЛУЧАТЕЛЬ ПРМ')

    def test_operator_keeps_enabled_zero_and_disabled_direction_blank(self):
        self.sub.channels.update(mailing_received=False,mailing_sent=False)
        self.add('Ноль ПРМ','РАМ',True,False,0,900,mail='')
        self.add('Ещё ноль','ЛХС',True,False,0,700,mail='')
        self.sub.channels.update(mailing_addresses='')
        sheet=self.export()['для Оператора']
        row=next(row for row in sheet if row[0].value=='Общий абонент')
        self.assertEqual(row[2].value,0)
        self.assertIsNone(row[3].value)
        self.assertIsNone(row[4].value)

    def test_template_unchanged_and_styles_dates_and_markers_preserved(self):
        from hashlib import sha256
        from openpyxl import load_workbook
        from .monthly_export import TEMPLATE
        before=sha256(TEMPLATE.read_bytes()).digest()
        source=load_workbook(TEMPLATE)
        result=self.export()
        self.assertEqual(result.sheetnames,source.sheetnames)
        self.assertEqual(result['ФГУП ГК']['B1'].value,source['ФГУП ГК']['B1'].value)
        self.assertEqual(result['Каналы ПД']['F4'].value,'=TODAY()')
        self.assertEqual(result['Каналы ПД']['B2'].value,'за май 2026')
        self.assertEqual(result['для согласования']['A7'].value,'ИТОГ РАБОТЫ ЗА май 2026')
        for name,cell in [('Каналы ПД','D7'),('для Оператора',f"C{template_marker_row('для Оператора', '#абонент')}")]:
            self.assertEqual(copy(result[name][cell].fill),copy(source[name][cell].fill))
            self.assertEqual(copy(result[name][cell].font),copy(source[name][cell].font))
            self.assertEqual(result[name][cell].number_format,source[name][cell].number_format)
        for sheet in result:
            for row in sheet:
                for cell in row:
                    if isinstance(cell.value,str):
                        self.assertFalse(cell.value.startswith('#'),(sheet.title,cell.coordinate))
        source.close()
        self.assertEqual(sha256(TEMPLATE.read_bytes()).digest(),before)

    def test_empty_month_keeps_headers_and_blanks_operator_values(self):
        sheet=self.export('month=2026-07')['для Оператора']
        start = template_marker_row('для Оператора', '#абонент')
        for column in (1,3,4,5):
            self.assertIsNone(sheet.cell(start,column).value)
        self.assertEqual(sheet.cell(start+1,3).value,f'=SUM(C{start}:C{start})')
        self.assertEqual(sheet.cell(start-1,1).value,'Абонент')

    def test_custom_positions_merges_formulas_and_cross_sheet_references(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill
        other=Subscriber.objects.create(name='Ещё один федеральный',category='federal')
        self.add('Дополнительный','',False,False,9,11,subscriber=other)
        with TemporaryDirectory() as folder:
            path=Path(folder)/'custom.xlsx'
            source=Workbook()
            sheet=source.active
            sheet.title='Произвольный'
            sheet['A1']='Период: #месяц #год'
            sheet.merge_cells('A1:D1')
            sheet['A4']='#федеральные'
            sheet['B4']='#user_received'
            sheet['C4']='#user_sent'
            sheet['D4']='#route_address'
            sheet['B4'].fill=PatternFill('solid',fgColor='DDEEFF')
            sheet['B5']='=SUM(B4:B4)'
            sheet['C5']='=SUM(C4:C4)'
            sheet['A7']='Подпись'
            sheet.print_area='A1:D7'
            summary=source.create_sheet('Свод')
            summary['A1']="='Произвольный'!B5"
            summary['A2']="=SUM('Произвольный'!B4:B4)"
            source.save(path)
            with patch('traffic_stats.monthly_export.TEMPLATE',path):
                book=self.export()
            sheet=book['Произвольный']
            self.assertEqual(sheet['A1'].value,'Период: май 2026')
            self.assertEqual({sheet['A4'].value,sheet['A5'].value},{self.sub.name,other.name})
            self.assertEqual(sheet['B6'].value,'=SUM(B4:B5)')
            self.assertEqual(sheet['A8'].value,'Подпись')
            self.assertIn('$D$8',str(sheet.print_area))
            self.assertIn('A1:D1',str(sheet.merged_cells))
            self.assertEqual(copy(sheet['B4'].fill),copy(sheet['B5'].fill))
            self.assertEqual(book['Свод']['A1'].value,"='Произвольный'!B6")
            self.assertEqual(book['Свод']['A2'].value,"=SUM('Произвольный'!B4:B5)")

    def test_unknown_template_marker_reports_clear_error(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        from openpyxl import Workbook
        with TemporaryDirectory() as folder:
            path=Path(folder)/'bad.xlsx'
            book=Workbook()
            book.active['A1']='#неизвестное_поле'
            book.save(path)
            with patch('traffic_stats.monthly_export.TEMPLATE',path):
                response=self.client.get('/statistics/?month=2026-05&download=all')
            self.assertEqual(response.status_code,400)
            self.assertContains(response,'Неизвестная метка #неизвестное_поле',status_code=400)

class StatisticsSignerTests(TestCase):
    def test_single_record_can_be_updated_but_not_duplicated(self):
        from django.core.exceptions import ValidationError
        from django.db import IntegrityError, transaction
        from .models import StatisticsSigner
        signer = StatisticsSigner.objects.create(position='Ведущий инженер', name='И.И. Иванов')
        signer.name = 'П.П. Петров'
        signer.save()
        with self.assertRaises(ValidationError):
            StatisticsSigner.objects.create(position='Другой', name='Другой')
        with self.assertRaises(ValidationError):
            StatisticsSigner(id=2, position='Другой', name='Другой').save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            StatisticsSigner.objects.bulk_create([StatisticsSigner(id=2, position='Другой', name='Другой')])
        self.assertEqual(StatisticsSigner.objects.get().name, 'П.П. Петров')

    def test_admin_add_only_when_empty_and_edit_existing(self):
        from django.contrib.auth import get_user_model
        from .models import StatisticsSigner
        user = get_user_model().objects.create_superuser('signer_admin', password='test')
        self.client.force_login(user)
        url = '/admin/traffic_stats/statisticssigner/'
        self.assertEqual(self.client.get(url+'add/').status_code, 200)
        response = self.client.post(url+'add/', {'position':'Инженер', 'name':'И.И. Иванов', '_save':'1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(url+'add/').status_code, 403)
        response = self.client.post(url+'1/change/', {'position':'Начальник', 'name':'П.П. Петров', '_save':'1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StatisticsSigner.objects.get().position, 'Начальник')

    def test_export_replaces_signer_markers_and_handles_missing_signer(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from .exports import load_export_dependencies
        from .models import StatisticsSigner
        from .monthly_export import export_monthly_workbook
        load_export_dependencies()
        from openpyxl import Workbook, load_workbook
        with TemporaryDirectory() as directory:
            template = Path(directory)/'template.xlsx'
            book = Workbook()
            book.active['A1'] = '#должность'
            book.active['A2'] = 'Подписал: #имя'
            book.save(template)
            with patch('traffic_stats.monthly_export.TEMPLATE', template):
                context = {'month':'2026-10', 'category_sections':[]}
                empty = load_workbook(BytesIO(export_monthly_workbook(context).content))
                self.assertIsNone(empty.active['A1'].value)
                StatisticsSigner.objects.create(position='Ведущий инженер', name='И.И. Иванов')
                result = load_workbook(BytesIO(export_monthly_workbook(context).content))
                self.assertEqual(result.active['A1'].value, 'Ведущий инженер')
                self.assertEqual(result.active['A2'].value, 'Подписал: И.И. Иванов')

class UploadDesignationTests(TestCase):
    def test_aftn_designation_follows_channel_and_amhs_has_no_extra_column(self):
        response = self.client.post('/statistics/upload/', {'action':'preview', 'file':SimpleUploadedFile('aftn.txt', AFTN.encode('utf-8'))})
        self.assertContains(response, '<th class="route-address">Адрес</th>')
        self.assertContains(response, '<th>Канал</th><th class="upload-designation">ПРД</th>', html=True)
        self.assertContains(response, '<td class="upload-designation">РАМ</td>', html=True)
        response = self.client.post('/statistics/upload/', {'action':'preview', 'file':SimpleUploadedFile('amhs.txt', AMHS.encode('utf-8'))})
        self.assertNotContains(response, '<th class="upload-designation">ПРД</th>')

class AftnRepeatedAddressTests(TestCase):
    repeated = AFTN + '\n080;ЛХС;УЛЛЛЫФЫА;Другое имя;10;20'

    def test_merges_non_adjacent_addresses_names_and_clears_designation(self):
        text = AFTN + '\n081;РРР;УЛЛЛЫФЫБ;Другой канал;3;4\n080;ЛХС;УЛЛЛЫФЫА;Другое имя;10;20'
        rows = parse(text)['rows']
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]['received'], rows[0]['sent']), (75, 117))
        self.assertEqual((rows[0]['number'], rows[0]['designation'], rows[0]['source_name']), ('079', '', 'Монитор / Другое имя'))
        self.assertEqual((rows[1]['received'], rows[1]['sent']), (3, 4))

    def test_preview_save_and_replacement_use_one_channel_record(self):
        for replacement in (False, True):
            if replacement:
                Channel.objects.update(name='Старое имя', transmission_designation='РАМ')
            response = self.client.post('/statistics/upload/', {'action':'preview', 'file':SimpleUploadedFile('aftn.txt', self.repeated.encode('utf-8'))})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['rows']), 1)
            self.assertEqual(response.context['rows'][0]['row']['received'], 75)
            self.assertContains(response, '<td class="upload-channel-name">Монитор / Другое имя</td>', html=True)
            token = self.client.session['stats_preview']['token']
            response = self.client.post('/statistics/upload/', {'action':'save', 'token':token, 'new_0':'Монитор', 'category_0':'other', 'replace':'yes'})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Channel.objects.count(), 1)
            self.assertEqual(Record.objects.count(), 1)
            record = Record.objects.get()
            self.assertEqual((record.received, record.sent), (75, 117))
            self.assertEqual(record.channel.transmission_designation, '')
            self.assertEqual(record.channel.name, 'Монитор / Другое имя')

    def test_duplicate_counters_are_validated_before_merging(self):
        for text in (self.repeated.replace(';10;20', ';-1;20'), self.repeated.replace(';10;20', ';9223372036854775807;20')):
            with self.assertRaises(ImportError):
                parse(text)

    def test_three_merged_names_and_oversized_name(self):
        rows = parse(self.repeated + '\n081;РРР;УЛЛЛЫФЫА;Третье имя;1;2')['rows']
        self.assertEqual(rows[0]['source_name'], 'Монитор / Другое имя / Третье имя')
        self.assertEqual(rows[0]['designation'], '')
        self.assertEqual((rows[0]['received'], rows[0]['sent']), (76, 119))
        with self.assertRaisesMessage(ImportError, 'Объединённое название'):
            parse(self.repeated.replace('Другое имя', 'А' * 200))

class ExportRowHeightTests(TestCase):
    def test_addresses_wrap_at_word_boundaries_without_clipping(self):
        from .exports import load_export_dependencies
        load_export_dependencies()
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from .monthly_export import _fit_row
        sheet = Workbook().active
        sheet.column_dimensions['F'].width = 17.140625
        sheet['F7'] = 'УЛЛЛТОЬТ, УЛЛЛЛОЬФ, УЛЛЛДОЬЬ, УЛЛЛПЬЬЬ'
        sheet['F7'].font = Font(name='Arial', size=10)
        _fit_row(sheet, 7)
        self.assertTrue(sheet['F7'].alignment.wrap_text)
        self.assertGreaterEqual(sheet.row_dimensions[7].height, 64)
        self.assertEqual(sheet['F7'].font.sz, 10)

    def test_explicit_newlines_and_merged_subscriber_name_fit(self):
        from .exports import load_export_dependencies
        load_export_dependencies()
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from .monthly_export import _fit_row
        sheet = Workbook().active
        sheet.column_dimensions['A'].width = 16
        sheet.column_dimensions['B'].width = 16
        sheet.merge_cells('A7:B7')
        sheet['A7'] = 'в/ч Каронит'
        sheet['C7'] = 'АДРЕС001\nАДРЕС002\nАДРЕС003\nАДРЕС004'
        sheet['C7'].font = Font(size=10)
        _fit_row(sheet, 7)
        self.assertGreaterEqual(sheet.row_dimensions[7].height, 64)
        self.assertEqual(sheet['A7'].value, 'в/ч Каронит')

    def test_short_text_preserves_explicit_and_default_height(self):
        from .exports import load_export_dependencies
        load_export_dependencies()
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from .monthly_export import _fit_row
        sheet = Workbook().active
        sheet.column_dimensions['A'].width = 32
        for row, height in ((1, 14.1), (2, 80), (3, None)):
            sheet.cell(row, 1, 'Канал')
            sheet.cell(row, 1).font = Font(size=10)
            sheet.row_dimensions[row].height = height
            _fit_row(sheet, row)
            self.assertEqual(sheet.row_dimensions[row].height, height)


class PastedStatisticsTests(TestCase):
    url = '/statistics/upload/'

    def test_two_reports_preview_and_save_together(self):
        amhs = AMHS.replace('01.10.2026-31.10.2026', '01.05.2026-31.05.2026')
        # Two formats may be pasted in either order with Windows line endings.
        response = self.client.post(self.url, {
            'action': 'preview', 'statistics_text': (amhs + '\n' + AFTN).replace('\n', '\r\n'),
        })
        self.assertEqual([section['report']['kind'] for section in response.context['sections']], ['AMHS', 'AFTN'])
        self.assertNotContains(response, 'id="statistics-text"')
        self.assertContains(response, 'name="new_0" value="MTA-UHPP-1"')
        self.assertContains(response, 'name="new_1" value="Монитор"')
        self.assertFalse(ImportBatch.objects.exists())
        token = self.client.session['stats_preview']['token']
        response = self.client.post(self.url, {'action': 'save', 'token': token, 'new_0': 'AMHS'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ImportBatch.objects.exists())
        self.assertFalse(Channel.objects.exists())
        response = self.client.post(self.url, {
            'action': 'save', 'token': token, 'new_0': 'AMHS', 'new_1': 'AFTN',
        })
        self.assertRedirects(response, '/statistics/?month=2026-05', fetch_redirect_response=False)
        self.assertEqual(set(Record.objects.values_list('batch__kind', 'received', 'sent')),
                         {('AFTN', 65, 97), ('AMHS', 108, 2)})

    def test_cannot_save_either_report_without_required_replacement_confirmation(self):
        ImportBatch.objects.create(month=date(2026, 5, 1), kind='AFTN', filename='before.txt', source='')
        response = self.client.post(self.url, {'action': 'preview', 'statistics_text': AFTN + '\n' + AMHS})
        self.assertContains(response, 'Подтверждаю полную замену AFTN за 2026-05')
        token = self.client.session['stats_preview']['token']
        response = self.client.post(self.url, {'action': 'save', 'token': token, 'new_0': 'AFTN', 'new_1': 'AMHS'})
        self.assertContains(response, 'Подтвердите полную замену')
        self.assertEqual(list(ImportBatch.objects.values_list('filename', flat=True)), ['before.txt'])

    def test_invalid_second_report_preserves_text_without_creating_preview(self):
        text = AFTN + '\nAMHS\nневерный период'
        response = self.client.post(self.url, {'action': 'preview', 'statistics_text': text})
        self.assertContains(response, 'Отчёт 2:')
        self.assertContains(response, 'id="statistics-text"')
        self.assertEqual(response.context['pasted_text'], text)
        self.assertNotIn('stats_preview', self.client.session)


class EditableHelpTests(TestCase):
    def test_staff_can_save_formatted_help_and_public_page_displays_it(self):
        from django.contrib.auth import get_user_model
        from django.contrib.flatpages.models import FlatPage

        url = '/statistics/help/'
        edit_url = url + 'edit/'
        page = self.client.get(url)
        self.assertContains(page, 'Изменить описание')
        self.assertContains(page, 'MTA-EXAMPLE-1')
        self.assertEqual(self.client.post(edit_url, {'description': '<p>Forbidden</p>'}).status_code, 302)
        self.assertFalse(FlatPage.objects.filter(url=url).exists())

        staff = get_user_model().objects.create_user(username='help-editor', is_staff=True)
        self.client.force_login(staff)
        self.assertContains(self.client.get(edit_url), 'MTA-EXAMPLE-1')
        html = '<h2>Инструкция</h2><p onclick="alert(1)"><b>Текст</b></p><ul><li>Строка</li></ul><script>alert(2)</script>'
        response = self.client.post(edit_url, {'description': html})
        self.assertRedirects(response, url)
        self.assertEqual(FlatPage.objects.get(url=url).content, '<h2>Инструкция</h2><p><b>Текст</b></p><ul><li>Строка</li></ul>')
        self.assertContains(self.client.post(edit_url, {'description': '<p><br></p>'}), 'Введите описание.')
        self.assertRedirects(self.client.post(edit_url, {'description': '<p><i>Обновлено</i></p>'}), url)
        self.client.logout()
        self.assertContains(self.client.get(url), '<p><i>Обновлено</i></p>', html=True)


    def test_jodit_text_formatting_survives_save(self):
        from django.contrib.auth import get_user_model

        staff = get_user_model().objects.create_user(username='font-editor', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post('/statistics/help/edit/', {
            'description': '<p style="text-align: center; line-height: 1.5">'
                           '<span style="font-family: Arial, Helvetica, sans-serif; font-size: 18px; position: fixed" onclick="x()">'
                           'Описание</span><span style="font-family: unknown; font-size: 900px">Пример</span></p>'
                           '<p style="text-align: unknown; line-height: 900px">Строка</p>',
        })
        self.assertRedirects(response, '/statistics/help/')
        page = self.client.get('/statistics/help/')
        self.assertContains(page, '<p style="text-align: center; line-height: 1.5"><span style="font-family: Arial, Helvetica, sans-serif; font-size: 18px">Описание</span>Пример</p>', html=True)
        self.assertNotContains(page, 'font-size: 900px')
        self.assertNotContains(page, 'text-align: unknown')
        self.assertNotContains(page, 'line-height: 900px')
        self.assertNotContains(page, 'position: fixed')
        self.assertNotContains(page, 'font-family: unknown')
        self.assertNotContains(page, 'onclick="x()"')


class MonthlyChartTests(TestCase):
    def test_range_chart_uses_effective_monthly_counts_and_current_filters(self):
        subscriber = Subscriber.objects.create(name='График', category='federal')
        aftn = Channel.objects.create(kind='AFTN', name='Канал 1', route_address='CHART001', subscriber=subscriber)
        amhs = Channel.objects.create(kind='AMHS', name='Канал 2', subscriber=subscriber)
        start = date(2026, 12, 1)
        end = date(2027, 2, 1)
        first = ImportBatch.objects.create(month=start, kind='AFTN')
        last = ImportBatch.objects.create(month=end, kind='AFTN')
        additional = ImportBatch.objects.create(month=start, kind='AMHS')
        Record.objects.create(batch=first, channel=aftn, received=10, sent=3, user_received=0)
        Record.objects.create(batch=last, channel=aftn, received=20, sent=4, user_sent=8)
        Record.objects.create(batch=additional, channel=amhs, received=5, sent=7)
        url = '/statistics/'
        period = {'month': '2026-12', 'end_month': '2027-02'}

        page = self.client.get(url, period)
        for scope in ('subscriber', 'category'):
            self.assertContains(page, f'data-chart-scope="{scope}"')
        self.assertNotContains(page, 'data-chart-scope="channel"')
        self.assertNotContains(self.client.get(url, {'month': '2026-12'}), 'stat-chart-button')

        response = self.client.get(url, dict(period, chart='subscriber', chart_id=subscriber.pk))
        self.assertEqual(response.json(), dict(period, points=[
            {'month': '2026-12', 'received': '5', 'sent': '10'},
            {'month': '2027-02', 'received': '20', 'sent': '8'},
        ]))
        for extra, expected in (
            ({'chart': 'channel', 'chart_id': aftn.pk}, '0'),
            ({'chart': 'category', 'chart_id': 'federal', 'kind': 'AFTN'}, '0'),
        ):
            self.assertEqual(self.client.get(url, dict(period, **extra)).json()['points'][0]['received'], expected)

        self.assertEqual(self.client.get(url, {'month': '2026-12', 'chart': 'category', 'chart_id': 'federal'}).status_code, 400)
        self.assertEqual(self.client.get(url, dict(period, chart='channel', chart_id='unknown')).status_code, 400)
