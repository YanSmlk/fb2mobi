#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from lxml import etree, html
import cgi
import re
import shutil
import io
import codecs
import uuid
import cssutils
import base64

from hyphenator import Hyphenator

SOFT_HYPHEN = u'\u00AD'  # Символ 'мягкого' переноса

CHAPTS_COUNT = 0 # Глобальная переменная для передачи значения в функцию rewrite_links
TEMP_DIR = u'' # Глобальная переменная для передачи значения в функцию rewrite_links


HTMLHEAD = (u'<?xml version="1.0"?>'
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
            '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<head>'
            '<title>fb2mobi.py</title>'
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
            '<link rel="stylesheet" type="text/css" href="stylesheet.css" />'
            '</head>'
            '<body>')

HTMLFOOT = (u'</body>'
            '</html>')

def transliterate(string):
    '''Транслитерация строки'''

    transtable =  {
        u'а' : 'a',
        u'б' : 'b',
        u'в' : 'v',
        u'г' : 'g',
        u'д' : 'd',
        u'е' : 'e',
        u'ё' : 'e',
        u'ж' : 'zh',
        u'з' : 'z',
        u'и' : 'i',
        u'й' : 'i',
        u'к' : 'k',
        u'л' : 'l',
        u'м' : 'm',
        u'н' : 'n',
        u'о' : 'o',
        u'п' : 'p',
        u'р' : 'r',
        u'с' : 's',
        u'т' : 't',
        u'у' : 'u',
        u'ф' : 'f',
        u'х' : 'h',
        u'ц' : 'c',
        u'ч' : 'ch',
        u'ш' : 'sh',
        u'щ' : 'csh',
        u'ъ' : "'",
        u'ы' : 'i',
        u'ь' : "'",
        u'э' : 'e',
        u'ю' : 'u',
        u'я' : 'ya',

        u'А' : 'A',
        u'Б' : 'B',
        u'В' : 'V',
        u'Г' : 'G',
        u'Д' : 'D',
        u'Е' : 'E',
        u'Ё' : 'E',
        u'Ж' : 'Zh',
        u'З' : 'Z',
        u'И' : 'I',
        u'Й' : 'I',
        u'К' : 'K',
        u'Л' : 'L',
        u'М' : 'M',
        u'Н' : 'N',
        u'О' : 'O',
        u'П' : 'P',
        u'Р' : 'R',
        u'С' : 'S',
        u'Т' : 'T',
        u'У' : 'U',
        u'Ф' : 'F',
        u'Х' : 'H',
        u'Ц' : 'C',
        u'Ч' : 'Ch',
        u'Ш' : 'Sh',
        u'Щ' : 'Csh',
        u'Ъ' : "'",
        u'Ы' : 'I',
        u'Ь' : "'",
        u'Э' : 'E',
        u'Ю' : 'U',
        u'Я' : 'YA'
    }

    translatedstring = []
    for c in string:
        translatedstring.append(transtable.setdefault(c, c))

    return ''.join(translatedstring)

def ns_tag(tag):
    '''Очистка имени тэга от namespace, заключенного в фигурные скобки {}'''

    if tag[0] == '{':
        tag = tag.split('}', 1)[1]
    return tag


def save_html(string):
    '''Преобразует специальные символы html, такие как угловые скобки, кавычки и т.п.
    в мнемонические конструкции html, типа &lt; &quot; и т.п.
    '''

    if string:
        return cgi.escape(string)
    else:
        return ''

def write_file(buff, filename):
    '''Сохраняет указанный строковый буфер в указанный файл.
    Если конечный каталог отсутствует, он предварительно создается.

    Параметры:
        buff - строковый буфер для сохранения
        filename - имя файла
   '''

    d = os.path.dirname(filename)
    if not os.path.exists(d):
        os.makedirs(d)

    with codecs.open(filename, 'w', 'utf-8') as f:
        f.write(buff)

def write_file_bin(buff, filename):
    '''Сохраняет указанный бинарный буфер в указанный файл.
    Если конечный каталог отсутствует, он предварительно создается.

    Параметры:
        buff - строковый буфер для сохранения
        filename - имя файла
   '''

    d = os.path.dirname(filename)
    if not os.path.exists(d):
        os.makedirs(d)

    with open(filename, 'wb') as f:
        f.write(buff)

def copy_file(src, dest):
    '''Копирует файл src в файл dest, если конечный каталог отсутствует,
    то он предварительно создается
    '''

    d = os.path.dirname(dest)
    if not os.path.exists(d):
        os.makedirs(d)

    shutil.copyfile(src, dest)

def indent(elem, level=0):
    '''Функция для улучшения вида xml/html.
    Вставляет символы табуляции согласно уровня вложенности тэга
    '''

    i = '\n' + level*'\t'
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + '\t'
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

class Fb2XHTML:
    '''Класс Fb2XHTML:
    Предоставляет методы для конвертации файла в формате Fb2 в набор файлов xhtml/xml, шрифтов, стилей и изображений,
    пригодных для ковертации в формат mobi (Kindle format 8) с помощью kindlegen, либо упаковки в формат epub
    '''
    def __init__(self, fb2file, mobifile, tempdir, config):
        self.buff = []
        self.current_header_level = 0   # Уровень текущего заголовка
        self.header = False     # Признак формирования заголовка
        self.subheader = False      # Признак формирования подзаголовка
        self.first_chapter_line = False     # Признак первой строки в главе (секции) - для расстановки dropcaps
        self.inline_image_mode = False      # Индикатор режима вставки картинок (inline)
        self.body_name = ''     # Имя текущего раздела body, например notes
        self.no_paragraph = False   # Индикатор, что последующий парагаф находится в эпиграфе, аннотации и т.п.
        self.first_header_in_body = True    # Признак первого заголовка в секции body

        self.book_title = ''    # Название книги
        self.book_author = ''   # Автор
        self.book_lang = 'ru'   # Язык книги, по-умолчанию 'ru'
        self.book_series = ''   # Книжная серия
        self.book_series_num = ''   # Номер в книжной серии
        self.book_cover = ''    # Ссылка на файл изображения обложки книги

        self.dropcaps = config.current_profile['dropcaps']      # Признак вставки стилей буквицы (dropcaps)
        self.nodropcaps = config.no_dropcaps_symbols  # Строка символов, для исключения буквицы
        # Максимальный уровень заголовка (секции) для помещения в содержание (toc.xhtml)
        # В toc.ncx помещаются все уровни
        self.toc_max_level = config.current_profile['tocMaxLevel'] if config.current_profile['tocMaxLevel'] else 1000000

        self.authorstring = config.current_profile['authorFormat']
        self.bookseriestitle = config.current_profile['bookTitleFormat']

        self.css_file = config.current_profile['css']
        self.parse_css = config.current_profile['parse_css']

        self.log = config.log

        self.annotation = None

        self.generate_toc_page = config.current_profile['generateTOCPage']
        self.generate_annotation_page = config.current_profile['generateAnnotationPage']
        self.generate_opf_guide = config.current_profile['generateOPFGuide']

        self.vignettes = config.current_profile['vignettes']
        self.vignette_files = []

        self.annotation_title = config.current_profile['annotationTitle']   # Заголовок для раздела аннотации
        self.toc_title = config.current_profile['tocTitle']     # Заголовок для раздела содержания

        self.chaptersplit = config.current_profile['chapterOnNewPage'] # Разделять на отдельные файлы по главам
        self.chapter_count = 0 # Счетчик глав (файлов)

        self.tocbeforebody = config.current_profile['tocBeforeBody']  # Положение содержания - в начале либо в конце книги
        self.transliterate_author_and_title = config.transliterate_author_and_title

        self.flat_toc = config.current_profile['flatTOC'] # Признак плоского (одноуровнего оглавления), либо иерархического

        self.toc = {}   # Содрержание, формируется по мере парсинга
        self.toc_index = 1      # Текущий номер раздела содержания
        # Имя текущего файла для записи текста книги в xhtml.
        self.current_file = 'index.xhtml'
        self.current_file_index = 0

        # Для включения сносок и комментариев в текст книги
        self.notes_dict = {}    # Словарь со сносками и комментариями
        self.notes_mode = config.current_profile['notesMode'] # Режим отображения сносок: inline, block
        self.notes_bodies = config.current_profile['notesBodies']
        self.current_notes = []  # Переменная для хранения текущей сноски

        self.temp_dir = tempdir     # Временный каталог для записи промежуточных файлов
        self.temp_content_dir = os.path.join(self.temp_dir, 'OEBPS')
        self.temp_inf_dir = os.path.join(self.temp_dir, 'META-INF')

        self.html_file_list = [] # Массив для хранения списка сгенерированных xhtml файлов
        self.image_file_list = [] # Массив для хранения списка картинок

        self.mobi_file = mobifile

        self.tree = etree.parse(fb2file, parser=etree.XMLParser(recover=True))
        self.root = self.tree.getroot()

        self.hyphenator = Hyphenator('ru')
        self.hyphenate = config.current_profile['hyphens']

        self.first_body = True  # Признак первого body
        self.font_list = []

        self.book_uuid = uuid.uuid4()

        self.links_location = {}

        if self.notes_mode in ('inline', 'block'):
            self.get_notes_dict('notes')

    def generate(self):
        for child in self.root:
            if ns_tag(child.tag) == 'description':
                self.parse_description(child)
            elif ns_tag(child.tag) == 'body':
                self.parse_body(child)
            elif ns_tag(child.tag) == 'binary':
                self.parse_binary(child)

        self.correct_links()
        if self.generate_toc_page:
            self.generate_toc()
        self.generate_cover()
        self.generate_ncx()

        if self.css_file:
            self.copy_css()

        for v in self.vignette_files:
            try:
                copy_file(v, os.path.join(os.path.join(self.temp_content_dir, 'vignettes'), os.path.split(v)[1]))
            except:
                self.log.warning(u'File {} not found.'.format(v))

        self.generate_opf()
        self.generate_container()
        self.generate_mimetype()

    def copy_css(self):
        base_dir = os.path.abspath(os.path.dirname(self.css_file))
        self.font_list = []

        def replaceUrl(url):
            source_file = os.path.abspath(os.path.join(base_dir, url))

            if os.path.splitext(url)[1].lower() in ('.ttf', '.otf'):
                dest_file = os.path.abspath(os.path.join(self.temp_content_dir, 'fonts', os.path.basename(source_file)))
                new_url = 'fonts/' + os.path.basename(url)
                self.font_list.append(new_url)
            else:
                dest_file = os.path.abspath(os.path.join(self.temp_content_dir, 'images', 'css_' + os.path.basename(source_file)))
                new_url = 'images/css_' + os.path.basename(url)

            try:
                copy_file(source_file, dest_file)
            except:
                self.log.error(u'File {0}, referred by css, not found.'.format(url))

            return new_url

        if self.parse_css:
            stylesheet = cssutils.parseFile(self.css_file)
            cssutils.replaceUrls(stylesheet, replaceUrl)
            write_file(str(stylesheet.cssText,'utf-8'), os.path.join(self.temp_content_dir, 'stylesheet.css'))
        else:
            copy_file(self.css_file, os.path.join(self.temp_content_dir, 'stylesheet.css'))

    def correct_links(self):
        for fl in self.html_file_list:
            parser = etree.XMLParser(encoding='utf-8')
            root = etree.parse(os.path.join(self.temp_content_dir, fl), parser).getroot()

            for elem in root.xpath('//xhtml:a', namespaces={'xhtml': 'http://www.w3.org/1999/xhtml'}):
                link = elem.attrib['href']

                if link.startswith('#'):
                    try:
                        elem.set('href', self.links_location[link[1:]] + link)
                    except:
                        pass

            self.buff = str.replace(str(etree.tostring(root, encoding='utf-8', method='xml', xml_declaration=True),'utf-8'),' encoding=\'utf-8\'','',1)

            self.current_file = fl
            self.write_buff_to_xhtml()

    def write_buff_to_xhtml(self):
        '''Сохраняет  текущий буфер в xhtml, предварительно обработав с помощью функции indent
        для удобочитаемости временных xhtml файлов.
        '''

        filename = os.path.join(self.temp_content_dir, self.current_file)

        if not os.path.exists(self.temp_content_dir):
            os.makedirs(self.temp_content_dir)

        parser = etree.XMLParser(encoding='utf-8')
        xhtml = etree.parse(io.StringIO(self.get_buff()), parser)
        indent(xhtml.getroot())
        xhtml.write(filename, encoding='utf-8', method='xml', xml_declaration=True)

    def write_buff_to_xml(self, filename):
        '''Сохраняет строку в формате xml в файл
        предварительно обработав с помощью функции indent.
        Для удобочитаемости временных xml файлов
        '''

        d = os.path.dirname(filename)
        if not os.path.exists(d):
            os.makedirs(d)

        parser = etree.XMLParser(encoding='utf-8')
        xml = etree.parse(io.StringIO(self.get_buff()), parser)
        indent(xml.getroot())
        xml.write(filename, encoding='utf-8', method='xml', xml_declaration=True)

    def parse_note_elem(self, elem):
        note_title = ''

        if ns_tag(elem.tag) == 'section' and 'id' in elem.attrib:
            id = elem.attrib['id']
            notetext = []
            self.buff = []

            for e in elem:
                if ns_tag(e.tag) == 'title':
                    note_title = etree.tostring(e, method='text', encoding='utf-8').decode('utf-8').strip()
                else:
                    notetext.append(etree.tostring(e, method='text', encoding='utf-8').decode('utf-8').strip())

            self.notes_dict[id] = (note_title, ' '.join(notetext))
            note_title = ''
        else:
            for e in elem:
                self.parse_note_elem(e)

    def get_notes_dict(self, body_names):
        self.notes_dict = {}
        note_title = None

        notes_bodies = self.notes_bodies.replace(' ', '').split(',')

        for item in self.root:
            if ns_tag(item.tag) == 'body':
                if 'name' in item.attrib:
                    if item.attrib['name'] in notes_bodies:
                        for section in item:
                            self.parse_note_elem(section)

    def get_vignette(self, level, type):
        vignette = None
        try:
            vignette = self.vignettes[level][type]
        except:
            try:
                vignette = self.vignettes['default'][type]
            except:
                pass

        found = False

        if vignette:
            for v in self.vignette_files:
                if v == vignette:
                    found = True
                    break

            if not found:
                self.vignette_files.append(vignette)

        if vignette:
            vignette = os.path.split(vignette)[1]

        return vignette

    def parse_description(self, elem):
        lastname = ''
        middlename = ''
        firstname = ''

        for e in elem:
            if ns_tag(e.tag) == 'title-info':
                for t in e:
                    if ns_tag(t.tag) == 'book-title':
                        if t.text:
                            self.book_title = t.text
                    elif ns_tag(t.tag) == 'lang':
                        if t.text:
                            self.book_lang = t.text
                        else:
                            self.book_lang = 'ru'
                        self.hyphenator = Hyphenator(self.book_lang)
                    elif ns_tag(t.tag) == 'coverpage':
                        for c in t:
                            if ns_tag(c.tag) == 'image':
                                for a in c.attrib:
                                    if ns_tag(a) == 'href':
                                        self.book_cover = 'images/' + c.attrib[a][1:]
                                        break

                    elif ns_tag(t.tag) == 'author':
                        if self.book_author == '':
                            for a in t:
                                if ns_tag(a.tag) == 'first-name':
                                    firstname = a.text
                                elif ns_tag(a.tag) == 'middle-name':
                                    middlename = a.text
                                elif ns_tag(a.tag) == 'last-name':
                                    lastname = a.text

                            self.book_author = self.authorstring
                            self.book_author = self.book_author.replace('#fi', '' if not firstname else firstname[0] + '.')
                            self.book_author = self.book_author.replace('#mi', '' if not middlename else middlename[0] + '.')
                            self.book_author = self.book_author.replace('#f', '' if not firstname else firstname.strip())
                            self.book_author = self.book_author.replace('#m', '' if not middlename else middlename.strip())
                            self.book_author = self.book_author.replace('#l', '' if not lastname else lastname.strip())
                            self.book_author = self.book_author.strip()

                    elif ns_tag(t.tag) == 'sequence':
                        if 'name' in t.attrib:
                            self.book_series = t.attrib['name']
                        if 'number' in t.attrib:
                            self.book_series_num = t.attrib['number']

                    elif ns_tag(t.tag) == 'annotation':
                        self.annotation = etree.tostring(t, method='text', encoding='utf-8').decode('utf-8').strip()

                        if self.generate_annotation_page:
                            self.buff = []
                            self.current_file = 'annotation.xhtml'
                            self.html_file_list.append(self.current_file)

                            self.buff.append(HTMLHEAD)
                            self.buff.append(u'<div class="annotation"><div class="h1">%s</div>' % self.annotation_title)
                            self.parse_format(t, 'div')
                            self.buff.append('</div>')
                            self.buff.append(HTMLFOOT)

                            self.write_buff_to_xhtml()

    def parse_binary(self, elem):
        filename = None
        if elem.attrib['id']:
            filename = elem.attrib['id']
            if not os.path.splitext(filename)[1]:
                filename = filename + '.jpg'
            write_file_bin(base64.b64decode(elem.text.encode('ascii')), os.path.join(os.path.join(self.temp_content_dir, 'images'), filename))
            self.image_file_list.append('images/' + filename)

    def parse_span(self, span, elem):
        self.parse_format(elem, 'span', span)

    def parse_emphasis(self, elem):
        self.parse_span('emphasis', elem)

    def parse_strong(self, elem):
        self.parse_span('strong', elem)

    def parse_strikethrough(self, elem):
        self.parse_span('strike', elem)

    def parse_style(self, elem):
        self.parse_format(elem, 'span')

    def parse_emptyline(self, elem):
        self.buff.append('<div class="emptyline" />')

    def parse_title(self, elem):
        toc_ref_id = 'tocref%s' % self.toc_index
        toc_title = etree.tostring(elem, method='text', encoding='utf-8').decode('utf-8').strip()
        p = re.compile('\[.*\]')    # Удалим остатки ссылок
        toc_title = p.sub('', toc_title)


        if not self.body_name or self.first_header_in_body:
            self.header = True
            self.first_chapter_line = True

            self.buff.append('<div class="titleblock" id="%s">' % toc_ref_id)

            if not self.body_name and self.first_header_in_body:
                vignette = self.get_vignette('h0', 'beforeTitle')
                if vignette:
                    self.buff.append('<div class="vignette_title_before"><img src="vignettes/{0}" /></div>'.format(vignette))

                self.parse_format(elem, 'div', 'h0')
                self.current_header_level = 0

                vignette = self.get_vignette('h0', 'afterTitle')
                if vignette:
                    self.buff.append('<div class="vignette_title_after"><img src="vignettes/{0}" /></div>'.format(vignette))

            else:
                level = 'h%s' % (self.current_header_level if self.current_header_level <= 6 else 6)

                vignette = self.get_vignette(level, 'beforeTitle')
                if vignette:
                    self.buff.append('<div class="vignette_title_before"><img src="vignettes/{0}" /></div>'.format(vignette))

                self.parse_format(elem, 'div', level)

                vignette = self.get_vignette(level, 'afterTitle')
                if vignette:
                    self.buff.append('<div class="vignette_title_after"><img src="vignettes/{0}" /></div>'.format(vignette))

            self.toc[self.toc_index] = ['%s#%s' % (self.current_file, toc_ref_id), toc_title, self.current_header_level, self.body_name]
        else:
            self.buff.append('<div class="titlenotes" id="%s">' % toc_ref_id)
            self.parse_format(elem, 'div')

        self.buff.append('</div>\n')
        self.first_header_in_body = False;
        self.toc_index += 1
        self.header = False

    def parse_subtitle(self, elem):
        self.subheader = True
        #self.first_chapter_line = True
        self.parse_format(elem, 'p', 'subtitle')
        self.subheader = False

    def parse_image(self, elem):
        img_id = None
        for a in elem.attrib:
            if ns_tag(a) == 'href':
                image = elem.attrib[a][1:]
                if not os.path.splitext(image)[1]:
                    image = image + '.jpg'
            elif ns_tag(a) == 'id':
                 img_id = elem.attrib[a]

        if self.inline_image_mode:
            if img_id:
                self.buff.append('<img id="%s" class="inlineimage" src="images/%s" alt="%s"/>' % (img_id, image, image))
            else:
                self.buff.append('<img class="inlineimage" src="images/%s" alt="%s"/>' % (image, image))
        else:
            if img_id:
                self.buff.append('<div id="%s" class="image">' % img_id)
            else:
                self.buff.append('<div class="image">')
            self.buff.append('<img src="images/%s" alt="%s"/>' % (image, image))
            self.buff.append('</div>')

        self.parse_format(elem)

    def parse_a(self, elem):
        self.parse_format(elem, 'a', 'anchor', href=elem.attrib['{http://www.w3.org/1999/xlink}href'])

    def parse_p(self, elem):
        ptag = None
        pcss = None

        if self.header:
            ptag = 'p'
            pcss = 'title'
        else:
            ptag = 'p'

        self.parse_format(elem, ptag, pcss)

    def parse_poem(self, elem):
        self.no_paragraph = True
        self.parse_format(elem, 'div', 'poem')
        self.no_paragraph = False

    def parse_stanza(self, elem):
        self.parse_format(elem, 'div', 'stanza')
        #self.buff.append('<br/>')

    def parse_v(self, elem):
        self.parse_format(elem, 'p')

    def parse_cite(self, elem):
        self.parse_format(elem, 'div', 'cite')

    def parse_textauthor(self, elem):
        self.no_paragraph = True
        self.parse_format(elem, 'div', 'text-author')
        self.no_paragraph = False

    def parse_annotation(self, elem):
        self.no_paragraph = True
        self.parse_format(elem, 'div', 'annotation')
        self.no_paragraph = False

    def parse_table(self, elem):
        self.buff.append('<table class="table"')
        for attr in elem.attrib:
            self.buff.append(' {0}="{1}"'.format(attr, elem.attrib[attr]))
        self.buff.append('>')
        self.parse_format(elem)
        self.buff.append('</table>')

    def parse_epigraph(self, elem):
        self.no_paragraph = True
        self.parse_format(elem, 'div', 'epigraph')
        self.no_paragraph = False

    def parse_code(self, elem):
        self.parse_format(elem, 'code')

    def parse_other(self, elem):
        self.parse_format(elem, ns_tag(elem.tag))

    def parse_section(self, elem):
        self.current_header_level = self.current_header_level + 1

        if not self.body_name:
            if self.chaptersplit:
                self.buff.append(HTMLFOOT)
                self.write_buff_to_xhtml()

                self.buff = []
                self.current_file_index += 1
                self.current_file = 'index{0}.xhtml'.format(self.current_file_index)
                self.html_file_list.append(self.current_file)
                self.buff.append(HTMLHEAD)


        self.parse_format(elem, tag = 'div', css = 'section')
        #self.parse_format(elem)

        if not self.body_name:
            level = 'h%s' % (self.current_header_level if self.current_header_level <= 6 else 6)
            vignette = self.get_vignette(level, 'chapterEnd')
            if vignette:
                self.buff.append('<p class="vignette_chapter_end"><img src="vignettes/{0}" /></p>'.format(vignette))


        self.current_header_level = self.current_header_level - 1
        if self.current_header_level < 0:
            self.current_header_level = 0

    def parse_date(self, elem):
        self.parse_format(elem, 'time')

    def parse_format(self, elem, tag = None, css = None, href=None):
        dodropcaps = False
        note_id = ''
        note = ''

        if elem.text:
            # Обработка dropcaps
            if self.dropcaps and self.first_chapter_line and not (self.header or self.subheader) and tag == 'p' and not self.body_name:
                if not self.no_paragraph:
                    if elem.text[0] not in self.nodropcaps:
                        dodropcaps = True
                        css = 'dropcaps'
                    self.first_chapter_line = False

        if self.notes_mode in ('inline', 'block') and tag == 'a':
            note_id = href[1:]
            try:
                note = self.notes_dict[note_id]
                self.current_notes.append(note)
                tag = 'span'
                css = '%sanchor' % self.notes_mode
                href = None
            except KeyError:
                note = ''

        if tag:
            self.buff.append('<%s' % tag)
            if css:
                self.buff.append(' class="%s"' % css)
            if 'id' in elem.attrib:
                self.buff.append(' id="%s"' % elem.attrib['id'])
                self.links_location[elem.attrib['id']] = self.current_file
            if href:
                self.buff.append(' href="%s"' % save_html(href))
        if tag:
            if css == 'section':
                self.buff.append(' />')
            else:
                self.buff.append('>')
            # Для inline-картинок
            if tag == 'p':
                self.inline_image_mode = True

        if elem.text:
            if self.hyphenator and self.hyphenate and not (self.header or self.subheader):
                hstring = ' '.join([self.hyphenator.hyphenate_word(w, SOFT_HYPHEN) for w in elem.text.split()])
                if elem.text[0].isspace():
                    hstring = ' ' + hstring
                if elem.text[-1].isspace():
                    hstring += ' '
            else:
                hstring = elem.text

            if dodropcaps:
                self.buff.append('<span class="dropcaps">%s</span>%s' % (hstring[0], save_html(hstring[1:])))
            else:
                self.buff.append(save_html(hstring))

        for e in elem:
            if ns_tag(e.tag) == 'title':
                self.parse_title(e)
            elif ns_tag(e.tag) == 'subtitle':
                self.parse_subtitle(e)
            elif ns_tag(e.tag) == 'epigraph':
                self.parse_epigraph(e)
            elif ns_tag(e.tag) == 'annotation':
                self.parse_annotation(e)
            elif ns_tag(e.tag) == 'section':
                self.parse_section(e)
            elif ns_tag(e.tag) == 'strong':
                self.parse_strong(e)
            elif ns_tag(e.tag) == 'emphasis':
                self.parse_emphasis(e)
            elif ns_tag(e.tag) == 'strikethrough':
                self.parse_strikethrough(e)
            elif ns_tag(e.tag) == 'style':
                self.parse_style(e)
            elif ns_tag(e.tag) == 'a':
                self.parse_a(e)
            elif ns_tag(e.tag) == 'image':
                self.parse_image(e)
            elif ns_tag(e.tag) == 'p':
                self.parse_p(e)
            elif ns_tag(e.tag) == 'poem':
                self.parse_poem(e)
            elif ns_tag(e.tag) == 'stanza':
                self.parse_stanza(e)
            elif ns_tag(e.tag) == 'v':
                self.parse_v(e)
            elif ns_tag(e.tag) == 'cite':
                self.parse_cite(e)
            elif ns_tag(e.tag) == 'empty-line':
                self.parse_emptyline(e)
            elif ns_tag(e.tag) == 'text-author':
                self.parse_textauthor(e)
            elif ns_tag(e.tag) == 'table':
                self.parse_table(e)
            elif ns_tag(e.tag) == 'code':
                self.parse_code(e)
            elif ns_tag(e.tag) == 'date':
                self.parse_date(e)
            elif ns_tag(e.tag) == 'tr':
                self.parse_table_element(e)
            elif ns_tag(e.tag) == 'td':
                self.parse_table_element(e)
            elif ns_tag(e.tag) == 'th':
                self.parse_table_element(e)
            else:
                self.parse_other(e);

        if tag:
            if css == 'section':
                pass
            else:
                self.buff.append('</%s>' % tag)
            # Для inline-картинок
            if tag == 'p':
                self.inline_image_mode = False

            if self.current_notes:
                if self.notes_mode == 'inline':
                    self.buff.append('<span class="inlinenote">[%s]</span>' % save_html(self.insert_hyphenation(''.join(self.current_notes[0][1]))))
                    self.current_notes = []
                elif self.notes_mode == 'block' and tag == 'p':
                    self.buff.append('<div class="blocknote">')
                    for note in self.current_notes:
                        if note[1]:
                            self.buff.append('<p><span class="notenum">%s) </span>%s</p>' %(note[0], save_html(self.insert_hyphenation(''.join(note[1])))))
                    self.buff.append('</div>')
                    self.current_notes = []

        if elem.tail:
            self.buff.append(save_html(self.insert_hyphenation(elem.tail)))


    def parse_table_element(self, elem):
        self.buff.append('<{0}'.format(ns_tag(elem.tag)))

        for attr in elem.attrib:
            self.buff.append(' {0}="{1}"'.format(attr, elem.attrib[attr]))

        self.buff.append('>')
        self.parse_format(elem)
        self.buff.append('</{0}>'.format(ns_tag(elem.tag)))


    def insert_hyphenation(self, string):
        hstring = ''

        if string:
            if self.hyphenator and self.hyphenate and not (self.header or self.subheader):
                hstring = ' '.join([self.hyphenator.hyphenate_word(w, SOFT_HYPHEN) for w in string.split()])
                if string[0].isspace():
                    hstring = ' ' + hstring
                if string[-1].isspace():
                    hstring += ' '
            else:
                hstring = string

        return hstring


    def parse_body(self, elem):
        self.body_name = elem.attrib['name'] if 'name' in elem.attrib else ''
        self.current_header_level = 0
        self.first_header_in_body = True
        self.current_file_index = 0

        if self.first_body:
            self.first_body = False
            self.body_name = ''

        self.buff = []
        self.buff.append(HTMLHEAD)

        if not self.body_name:
            self.current_file = 'index{0}.xhtml'.format(self.current_file_index)
            self.html_file_list.append(self.current_file)
        else:
            self.current_file = '{0}.xhtml'.format(self.body_name)
            self.html_file_list.append(self.current_file)

        if self.notes_mode in ('inline', 'block'):
            notes_bodies = self.notes_bodies.replace(' ', '').split(',')
            if self.body_name not in notes_bodies:
                self.parse_format(elem)
        else:
            self.parse_format(elem)

        self.buff.append(HTMLFOOT)
        self.write_buff_to_xhtml()

    def generate_toc(self):
        self.buff = []
        self.buff.append(HTMLHEAD)
        self.current_file = 'toc.xhtml'

        if self.chapter_count > 0:
            for (idx, item) in self.toc.items():
                link = '#' + item[0].split('#')[1]
                self.toc[idx] = [repl_link(link), item[1], item[2], item[3]]

        self.buff.append('<div class="toc">')
        self.buff.append(u'<div class="h1" id="toc">%s</div>' % self.toc_title)
        for (idx, item) in self.toc.items():

            if item[2] <= self.toc_max_level: # Ограничение уровня вложенности секций для TOC
                if item[3] == '':
                    indent = item[2] if item[2] <= 6 else 6;

                    if indent == 0:
                        lines = item[1].splitlines()
                        self.buff.append('<div class="indent0"><a href="%s">' % item[0])
                        for line in lines:
                            if line.strip():
                                self.buff.append(line.strip() + '<br/>')
                        self.buff.append('</a></div>')
                    else:
                        self.buff.append(u'<div class="indent%s"><a href="%s">%s</a></div>' % (indent, item[0], save_html(' '.join(item[1].split()))))
                else:
                    self.buff.append(u'<div class="indent0"><a href="%s">%s</a></div>' % (item[0], save_html(' '.join(item[1].split()))))

        self.buff.append('</div>')
        self.buff.append(HTMLFOOT)

        self.write_buff_to_xhtml()
        self.html_file_list.append(self.current_file)

    def generate_ncx(self):
        self.buff = []
        self.buff.append('<?xml version="1.0"?>'
                         '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="en-US">'
                         '<head>')
        self.buff.append('<meta name="dtb:uid" content="urn:uuid:{0}"/>'.format(self.book_uuid))
        self.buff.append('</head>'
                         '<docTitle>'
                         '<text>fb2mobi.py</text>'
                         '</docTitle>'
                         '<navMap>')
        i = 1

        # Включим содержание в навигацию, если содержание помещается в начале книги
        if self.tocbeforebody and self.toc.items() > 0 and self.generate_toc_page:
            self.buff.append('<navPoint id="navpoint%s" playOrder="%s">' % (i, i))
            self.buff.append(u'<navLabel><text>Содержание</text></navLabel>')
            self.buff.append('<content src="toc.xhtml" />')
            self.buff.append('</navPoint>')
            i += 1

        if self.flat_toc:
            for(idx, item) in self.toc.items():
                self.buff.append('<navPoint id="navpoint%s" playOrder="%s">' % (i, i))
                self.buff.append('<navLabel><text>%s</text></navLabel>' % save_html(' '.join(item[1].split())))
                self.buff.append('<content src="%s" />' % item[0])
                self.buff.append('</navPoint>')
                i += 1
        else:
            current_level = -1
            for(idx, item) in self.toc.items():
                while current_level > item[2]:
                    self.buff.append('</navPoint>')
                    current_level -= 1

                if current_level == item[2]:
                    self.buff.append('</navPoint>')

                self.buff.append('<navPoint id="navpoint%s" playOrder="%s">' % (i, i))
                self.buff.append('<navLabel><text>%s</text></navLabel>' % save_html(' '.join(item[1].split())))
                self.buff.append('<content src="%s" />' % item[0])
                current_level = item[2]
                i += 1

            while current_level >= 0:
                self.buff.append('</navPoint>')
                current_level -= 1

        # Включим содержание в навигацию, если содержание помещается в конце книги
        if not self.tocbeforebody and len(self.toc.items()) > 0 and self.generate_toc_page:
            self.buff.append('<navPoint id="navpoint%s" playOrder="%s">' % (i, i))
            self.buff.append(u'<navLabel><text>Содержание</text></navLabel>')
            self.buff.append('<content src="toc.xhtml" />')
            self.buff.append('</navPoint>')

        self.buff.append('</navMap></ncx>')
        self.write_buff_to_xml(os.path.join(self.temp_content_dir, 'toc.ncx'))

    def generate_mimetype(self):
        mimetype = 'application/epub+zip'
        write_file(mimetype, os.path.join(self.temp_dir, 'mimetype'))

    def generate_container(self):
        self.buff = []
        self.buff.append('<?xml version="1.0"?>'
                         '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                         '<rootfiles>'
                         '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                         '</rootfiles>'
                         '</container>')
        self.write_buff_to_xml(os.path.join(self.temp_inf_dir, 'container.xml'))


    def generate_cover(self):
        if self.book_cover:
            self.buff = []
            self.buff.append(HTMLHEAD)
            self.buff.append('<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100%" height="100%" viewBox="0 0 573 800" preserveAspectRatio="xMidYMid meet">')
            self.buff.append('<image width="573" height="800" xlink:href="{0}" />'.format(self.book_cover))
            self.buff.append('</svg>')
            self.buff.append(HTMLFOOT)
            self.current_file = 'cover.xhtml'

            self.write_buff_to_xhtml()

    def generate_opf(self):
        self.buff = []
        self.buff.append('<?xml version="1.0" ?>'
                         '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId">'
                         '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">')
        if self.book_series == '':
            title = self.book_title
        else:
            abbr = ''.join(word[0] for word in self.book_series.split())
            title = self.bookseriestitle
            title = title.replace('#series', '' if not self.book_series else self.book_series.strip())
            title = title.replace('#number', '' if not self.book_series_num else self.book_series_num.strip())
            title = title.replace('#title', '' if not self.book_title else self.book_title.strip())
            title = title.replace('#abbrseries', '' if not abbr else abbr.lower())

        book_author = self.book_author

        if self.transliterate_author_and_title:
            title = transliterate(title)
            book_author = transliterate(book_author)


        self.buff.append('<dc:title>%s</dc:title>' % title)
        self.buff.append('<dc:language>%s</dc:language>' % self.book_lang)
        self.buff.append('<dc:identifier id="BookId" opf:scheme="uuid">urn:uuid:{0}</dc:identifier>'.format(self.book_uuid))
        self.buff.append('<dc:creator opf:role="aut">%s</dc:creator>' % book_author)
        self.buff.append('<dc:publisher />')

        if self.annotation:
            self.buff.append(u'<dc:description>{0}</dc:description>'.format(save_html(self.annotation)))

        if self.book_cover:
            self.buff.append('<meta name="cover" content="cover-image" />')

        self.buff.append('</metadata>')
        self.buff.append('<manifest>'
                         '<item id="ncx" media-type="application/x-dtbncx+xml" href="toc.ncx"/>')
        for item in self.html_file_list:
            self.buff.append('<item id="{0}" media-type="application/xhtml+xml" href="{1}"/>'.format(item.split('.')[0], item))

        item_id = 0
        for item in self.image_file_list:
            item_type = os.path.splitext(os.path.split(item)[1])[1]
            item_type = item_type[1:]

            if item_type == 'jpg':
                item_type = 'jpeg'

            if item == self.book_cover:
                self.buff.append('<item id="cover-image" media-type="image/{0}" href="{1}"/>'.format(item_type, item))
                self.buff.append('<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>')
            else:
                self.buff.append('<item id="image{0}" media-type="image/{1}" href="{2}"/>'.format(item_id, item_type, item))

            item_id += 1

        for item in self.vignette_files:
            item_file = os.path.split(item)[1]
            item_type = os.path.splitext(item_file)[1]
            item_type = item_type[1:]

            if item_type == 'jpg':
                item_type = 'jpeg'

            self.buff.append('<item id="image{0}" media-type="image/{1}" href="vignettes/{2}"/>'.format(item_id, item_type, item_file))
            item_id += 1

        self.buff.append('<item id="style" href="stylesheet.css" media-type="text/css"/>')

        font_id = 0
        for f in self.font_list:
            if f.lower().endswith('.otf'):
                self.buff.append('<item id="font{0}" href="{1}" media-type="application/opentype"/>'.format(font_id, f))
            else:
                self.buff.append('<item id="font{0}" href="{1}" media-type="application/x-font-ttf"/>'.format(font_id, f))
            font_id += 1

        self.buff.append('</manifest>'
                         '<spine toc="ncx">')

        if self.book_cover:
            self.buff.append('<itemref idref="cover-page" linear="no"/>')
        if self.tocbeforebody and self.generate_toc_page:
            self.buff.append('<itemref idref="toc"/>')

        for item in self.html_file_list:
            if item != 'toc.xhtml':
                self.buff.append('<itemref idref="{0}"/>'.format(item.split('.')[0]))

        if not self.tocbeforebody and self.generate_toc_page:
            self.buff.append('<itemref idref="toc"/>')

        self.buff.append('</spine>')

        if self.generate_opf_guide:
            self.buff.append('<guide>')
            if self.book_cover:
                self.buff.append('<reference type="cover-page" href="cover.xhtml" />')

            self.buff.append('<reference type="text" title="book" href="index0.xhtml"/>')
            self.buff.append('<reference type="toc" title="toc" href="toc.xhtml"/>')
            self.buff.append('</guide>')

        self.buff.append('</package>')

        self.write_buff_to_xml(os.path.join(self.temp_content_dir, 'content.opf'))

    def get_buff(self):
        return u''.join(self.buff)