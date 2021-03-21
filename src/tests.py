import TexSoup

ts = TexSoup.TexSoup(
    r'''\exg.\label{gl:label}
\a. No gloss
\bg. This is a first gloss\\
Dies ist eine erste Glosse\\
''')

for el in ts.contents:
    print(type(el))
    if type(el) == TexSoup.data.TexNode:
        print(repr(el.contents))
    else:
        print(repr(el))
