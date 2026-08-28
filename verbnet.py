import os
import xml.etree.ElementTree as ET


def parse(path):
    dirname = os.path.dirname(__file__)
    path = os.path.join(dirname, path)
    return ET.parse(path)


say = parse('new_vn/say-37.7.xml')
conjecture = parse('new_vn/conjecture-29.5.xml')
care = parse('new_vn/care-88.1.xml')
consider = parse('new_vn/consider-29.9.xml')
begin = parse('new_vn/begin-55.1.xml')
stop = parse('new_vn/stop-55.4.xml')
sustain = parse('new_vn/sustain-55.6.xml')


root = say.getroot()
say_hyponyms = []
for member in root.findall(".//MEMBER"):
    say_hyponyms.append(member.get("name"))
#print(say_hyponyms)

root = conjecture.getroot()
conjecture_hyponyms = []
for member in root.findall(".//MEMBER"):
    conjecture_hyponyms.append(member.get("name"))
#print(conjecture_hyponyms)

root = care.getroot()
care_hyponyms = []
for member in root.findall(".//MEMBER"):
    care_hyponyms.append(member.get("name"))
#print(care_hyponyms)

root = consider.getroot()
consider_hyponyms = []
for member in root.findall(".//MEMBER"):
    consider_hyponyms.append(member.get("name"))
#print(consider_hyponyms)

root = begin.getroot()
begin_hyponyms = []
for member in root.findall(".//MEMBER"):
    begin_hyponyms.append(member.get("name"))
#print(begin_hyponyms)

root = stop.getroot()
stop_hyponyms = []
for member in root.findall(".//MEMBER"):
    stop_hyponyms.append(member.get("name"))
#print(stop_hyponyms)

root = sustain.getroot()
sustain_hyponyms = []
for member in root.findall(".//MEMBER"):
    sustain_hyponyms.append(member.get("name"))
#print(sustain_hyponyms)
