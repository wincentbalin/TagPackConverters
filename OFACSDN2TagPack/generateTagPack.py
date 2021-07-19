import re
import json
import yaml
import datetime
import requests

ALIASES = {"XBT": "BTC"}

REGEX = {"BTC": r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})|bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87})\b",
         "BCH": r"\b(((?:bitcoincash|bchtest):)?([13][0-9a-zA-Z]{33}))|(((?:bitcoincash|bchtest):)?(qp)?[0-9a-zA-Z]{40})\b",
         "LTC": r"\b([LM3][a-km-zA-HJ-NP-Z1-9]{25,33})\b",
         "ZEC": r"\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b",
         "ETH": r"\b((0x)?[0-9a-fA-F]{40})\b"}

class Convert():
    @staticmethod
    def load_config():
        with open("config.json", "r") as json_data_file:
            config = json.load(json_data_file)
        return config

    @staticmethod
    def add_tag(address, label, currency, category):
        tag = {"address": address, "label": label, "currency": currency, "category": category}
        return tag

    @staticmethod
    def checkValidAddress(assetCode, address):
        try:
            matched = re.match(REGEX[assetCode], address)
            if matched == None:
                print("Is this a valid address?: %s (%s)" % (address, assetCode))
        except:
            print("Is this a valid address?: %s (%s)" % (address, assetCode))

    @staticmethod
    def add_details(raw_data, label, category):
        tags = []
        lines = raw_data.replace("\n", " ").split(";")
        for line in lines:
            if "Digital Currency Address" in line:
                splitted = line.lstrip().replace("alt. ", "").split(" ")
                (address, assetCode) = (splitted[5], splitted[4])
                isAddressRegistered = False
                for tag in tags:
                    if address == tag["address"]:
                        isAddressRegistered = True
                        break
                if isAddressRegistered:
                    continue
                for alias in ALIASES:
                    if assetCode == alias:
                        assetCode = ALIASES[assetCode]
                Convert.checkValidAddress(assetCode, address)
                tags += [Convert.add_tag(address, label, assetCode, category)]
        return tags

    @staticmethod
    def add_tags():
        config = Convert.load_config()
        if "source" not in config or "label" not in config or "creator" not in config or "category" not in config or "title" not in config:
            print("config.json file needs to define a title, a source, a label, a category and a creator")
            return
        timestamp = datetime.datetime.now()
        out = {"creator": config["creator"],
                "title": config["title"],
                "description": "Tagpack automatically created with the INTERPOL CNTL scraping tool",
                "lastmod": str(timestamp),
                "source": config["source"]}
        try:
           with requests.get(config["source"]) as source:
               raw_data = source.text
               tags = Convert.add_details(raw_data, config["label"], config["category"])
        except requests.exceptions.ConnectionError as exc:
           print(exc)
        out["tags"] = tags
        return out

if __name__ == "__main__":
    out = Convert.add_tags()
    #print(yaml.dump(out, sort_keys=False))
    with open("OFAC.yaml", "w") as fout:
        yaml.dump(out, fout, sort_keys=False)
