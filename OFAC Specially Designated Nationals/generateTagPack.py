import re
import os
import datetime
import xml.etree.ElementTree as ET
from typing import Union

import requests
import yaml

ALIASES = {"XBT": "BTC", "TRX": "USDT"}

REGEX = {"XBT": r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})|bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87})\b",
         "BCH": r"\b(((?:bitcoincash|bchtest):)?([13][0-9a-zA-Z]{33}))|(((?:bitcoincash|bchtest):)?(qp)?[0-9a-zA-Z]{40})\b",
         "LTC": r"\b([LM3][a-km-zA-HJ-NP-Z1-9]{25,33})\b",
         "ZEC": r"\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b",
         "ETH": r"\b((0x)?[0-9a-fA-F]{40})\b",
         "TRX": r"\b(?:T[A-Za-z1-9]{33}|0x[0-9a-fA-F]{40})\b"}

for c1, c2 in ALIASES.items():
    REGEX[c2] = REGEX[c1]

def find_currency(address: str) -> Union[str, None]:
    for currency, regex in REGEX.items():
        if re.match(regex, address):
            return currency
    return None


NS = {
    "schema": "http://www.w3.org/2001/XMLSchema-instance",
    "sdn": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML"
}


class RawData:
    """
    Download and read data provided by the source.
    """

    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url
        self.tree = ET.parse(self.fn) if os.path.exists(self.fn) else ET.fromstring('')

    def download(self):
        with requests.get(self.url, allow_redirects=True, verify=False) as source:
            source.raise_for_status()
            with open(self.fn, "wb") as fout:
                fout.write(source.content)
            self.tree = ET.fromstring(source.text)

    def get_date(self) -> str:
        pd = self.tree.find('./sdn:publshInformation/sdn:Publish_Date', NS)
        return datetime.datetime.strptime(pd.text, "%m/%d/%Y").date().isoformat()

    def get_tree(self) -> ET.ElementTree:
        return self.tree


class TagPackGenerator:
    """
    Generate a TagPack from Seizures of Cryptocurrency list.
    """

    def __init__(self, tree: Union[ET.ElementTree, str], title: str, creator: str, description: str, lastmod: str, source: str):
        self.tree = ET.parse(tree) if type(tree) == str else tree
        self.data = {
            'title': title,
            'creator': creator,
            'description': description,
            'lastmod': lastmod,
            'source': source,
            'category': 'perpetrator',
            'abuse': 'terrorism',
            'tags': []
        }
        self.description = description

    def generate(self):
        tags = []
        root = self.tree.getroot()
        for sdn_entry in root.findall('./sdn:sdnEntry', NS):
            id_list = sdn_entry.find('./sdn:idList', NS)
            if id_list is None:
                continue
            cryptocurrency_entries = []
            for id_entry in id_list.findall('./sdn:id', NS):
                id_type = id_entry.find('./sdn:idType', NS)
                if not id_type.text.startswith('Digital Currency Address'):
                    continue
                id_number = id_entry.find('./sdn:idNumber', NS)
                cryptocurrency_entries.append((id_type.text, id_number.text))
            if not cryptocurrency_entries:
                continue
            # Validate cryptocurrency addresses
            validated_addresses = []
            for type_text, number_text in cryptocurrency_entries:
                currency = type_text.removeprefix('Digital Currency Address - ')
                if currency not in REGEX:
                    print(f'Currency {currency} for address {number_text} is not supported yet')
                    continue
                if not re.match(REGEX[currency], number_text):
                    currency_found = find_currency(number_text)
                    if currency_found is None:
                        print(f'Address {number_text} does not match currency {currency}')
                        continue
                    else:
                        print(f'Address {number_text} had currency {currency} listed but is actually {currency_found}')
                    currency = currency_found
                if currency in ALIASES:
                    currency = ALIASES[currency]
                validated_addresses.append((currency, number_text))
            if not validated_addresses:
                continue
            # Create label
            last_name = sdn_entry.find('./sdn:lastName', NS)
            sdn_type = sdn_entry.find('./sdn:sdnType', NS)
            if sdn_type.text == 'Individual':
                first_name = sdn_entry.find('./sdn:firstName', NS)
                label = f'{self.description}; Individual: {first_name.text} {last_name.text}'
            elif sdn_type.text == 'Entity':
                label = f'{self.description}; Entity: {last_name.text}'
            else:
                print(f'Unknown SDN type {sdn_type.text}')
                continue
            country = sdn_entry.find('./sdn:addressList/sdn:address/sdn:country', NS)
            if country is not None:
                label = f'{label}, {country.text}'
            else:
                country = sdn_entry.find('./sdn:nationalityList/sdn:nationality[sdn:mainEntry="true"]/sdn:country', NS)
                if country is not None:
                    label = f'{label}, {country.text}'
            remarks = sdn_entry.find('./sdn:remarks', NS)
            if remarks is not None:
                label = f'{label} {remarks.text}'
            for currency, address in validated_addresses:
                tags.append({'label': label, 'currency': currency, 'address': address})
            self.data['tags'] = tags

    def saveYaml(self, fn: str):
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(yaml.dump(self.data, sort_keys=False))


if __name__ == "__main__":
    with open('config.yaml', 'r') as config_file:
        config = yaml.safe_load(config_file)

    raw_data = RawData(config['RAW_FILE_NAME'], config['URL'])
    if not os.path.exists(config['RAW_FILE_NAME']):
        raw_data.download()

    last_mod = raw_data.get_date()
    generator = TagPackGenerator(raw_data.get_tree(), config['TITLE'], config['CREATOR'], config['LABEL'],
                                 last_mod, config['URL'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])