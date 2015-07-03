
test: pytest xmltest

pytest:
	python -m unittest -v fgcz_biobeamer
	python -m unittest -v testBioBeamerParser

xmltest:
	xmllint --noout --schema BioBeamer.xsd BioBeamer.xml

