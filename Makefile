
test: pytest xmltest

pytest:
	python3 -m unittest discover -v -s tests

xmltest:
	xmllint --noout --schema configs/BioBeamer2.xsd configs/BioBeamer2.xml

