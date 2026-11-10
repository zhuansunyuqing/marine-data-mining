"""Set ordinary report text to SimSun without changing text or math structures."""
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
NS = {'w': W, 'a': A, 'm': M}


def is_math(element):
    return any(etree.QName(node).namespace == M for node in element.iterancestors())


def set_fonts(props):
    fonts = props.find('w:rFonts', NS)
    if fonts is None:
        fonts = etree.Element('{' + W + '}rFonts')
        props.insert(0, fonts)
    fonts.attrib.clear()
    for key in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
        fonts.set('{' + W + '}' + key, '宋体')
    fonts.set('{' + W + '}hint', 'eastAsia')
    lang = props.find('w:lang', NS)
    if lang is None:
        lang = etree.SubElement(props, '{' + W + '}lang')
    lang.attrib.clear()
    lang.set('{' + W + '}val', 'zh-CN')
    lang.set('{' + W + '}eastAsia', 'zh-CN')


def without_font_properties(root):
    copied = deepcopy(root)
    for elem in copied.xpath('//w:rFonts|//w:lang', namespaces=NS):
        if not is_math(elem):
            elem.getparent().remove(elem)
    for elem in copied.xpath('//w:rPr', namespaces=NS):
        if not len(elem) and not elem.attrib and not (elem.text or '').strip():
            elem.getparent().remove(elem)
    return etree.tostring(copied, method='c14n')


def normalize_report_fonts(path):
    path = Path(path)
    with ZipFile(path) as archive:
        items = [(item, archive.read(item.filename)) for item in archive.infolist()]
    updated = []
    changed = []
    for info, data in items:
        name = info.filename
        if not (name.startswith('word/') and name.endswith('.xml')):
            updated.append((info, data))
            continue
        root = etree.fromstring(data)
        before = etree.tostring(root, method='c14n')
        content_before = without_font_properties(root)
        # All ordinary direct and inherited formatting is explicit. Native
        # mathematical runs and their Cambria Math settings are untouched.
        for run in root.xpath('//w:r', namespaces=NS):
            if is_math(run):
                continue
            if run.find('w:rPr', NS) is None:
                run.insert(0, etree.Element('{' + W + '}rPr'))
        for props in root.xpath('//w:rPr', namespaces=NS):
            if not is_math(props):
                set_fonts(props)
        for lang in root.xpath('//w:lang', namespaces=NS):
            if not is_math(lang):
                lang.attrib.clear()
                lang.set('{' + W + '}val', 'zh-CN')
                lang.set('{' + W + '}eastAsia', 'zh-CN')
        if name == 'word/settings.xml':
            theme_lang = root.find('w:themeFontLang', NS)
            if theme_lang is not None:
                theme_lang.attrib.clear()
                theme_lang.set('{' + W + '}val', 'zh-CN')
                theme_lang.set('{' + W + '}eastAsia', 'zh-CN')
        if name.startswith('word/theme/'):
            for font in root.xpath('//a:fontScheme//a:latin|//a:fontScheme//a:ea|//a:fontScheme//a:cs|//a:fontScheme//a:font', namespaces=NS):
                font.set('typeface', '宋体')
        if name == 'word/fontTable.xml' and not root.xpath('w:font[@w:name="宋体"]', namespaces=NS):
            font = etree.SubElement(root, '{' + W + '}font')
            font.set('{' + W + '}name', '宋体')
            for tag, value in (('altName', 'SimSun'), ('charset', '86'), ('family', 'roman'), ('pitch', 'variable')):
                item = etree.SubElement(font, '{' + W + '}' + tag)
                item.set('{' + W + '}val', value)
        if name not in ('word/settings.xml', 'word/fontTable.xml') and not name.startswith('word/theme/'):
            assert content_before == without_font_properties(root), 'Non-font change: ' + name
        if before != etree.tostring(root, method='c14n'):
            data = etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
            changed.append(name)
        updated.append((info, data))
    with NamedTemporaryFile(dir=path.parent, suffix='.docx', delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(temporary, 'w') as archive:
            for info, data in updated:
                archive.writestr(info, data)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return changed


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'AIS空间活动变化的缺测敏感性研究_提交稿.docx'
    print('Font-only updates: ' + ', '.join(normalize_report_fonts(target)))
