# The tests work in JAR's setup...

# You'll need to put a copy of the previous (or baseline) version of OTT in tax/prev_ott/.
# This is a manual step.
# Get it from http://files.opentreeoflife.org/ott/

#  $^ = all prerequisites
#  $< = first prerequisite
#  $@ = file name of target

# Modify as appropriate to your own hardware - I set it one or two Gbyte
# below physical memory size
JAVAFLAGS=-Xmx14G

# Modify as appropriate
WHICH=2.10draft3
PREV_WHICH=2.9

# ----- Taxonomy source locations -----

# 12787947 Oct  6  2015 taxonomy.tsv
FUNG_URL=http://files.opentreeoflife.org/fung/fung-9/fung-9-ot.tgz

WORMS_URL=http://files.opentreeoflife.org/worms/worms-1/worms-1-ot.tgz

NCBI_URL="http://files.opentreeoflife.org/ncbi/ncbi-20151006/ncbi-20151006.tgz"

# Was http://ecat-dev.gbif.org/repository/export/checklist1.zip
# Could be http://rs.gbif.org/datasets/backbone/backbone.zip
# 2016-05-17 purl.org is broken, cannot update this link
# GBIF_URL=http://purl.org/opentree/gbif-backbone-2013-07-02.zip
GBIF_URL=http://files.opentreeoflife.org/gbif/gbif-20130702/gbif-20130702.zip

IRMNG_URL=http://files.opentreeoflife.org/irmng-ot/irmng-ot-20160628/irmng-ot-20160628.tgz

# Silva 115: 206M uncompresses to 817M
# issue #62 - verify  (is it a tsv file or csv file?)
# see also http://www.arb-silva.de/no_cache/download/archive/release_115/ ?

SILVA_EXPORTS=ftp://ftp.arb-silva.de/release_115/Exports
SILVA_URL=$(SILVA_EXPORTS)/SSURef_NR99_115_tax_silva.fasta.tgz

# This is used as a source of OTT id assignments.
PREV_OTT_URL=http://files.opentreeoflife.org/ott/ott$(PREV_WHICH)/ott$(PREV_WHICH).tgz

# -----

# Where to put tarballs
#TARDIR=/raid/www/roots/opentree/ott
TARDIR?=tarballs

# Scripts and other inputs related to taxonomy

# The tax/ directory is full of taxonomies; mostly (entirely?) derived objects.
SILVA=tax/silva
FUNG=tax/fung

CP=-classpath ".:lib/*"
JAVA=JYTHONPATH=util java $(JAVAFLAGS) $(CP)
SMASH=org.opentreeoflife.smasher.Smasher
CLASS=org/opentreeoflife/smasher/Smasher.class
JAVASOURCES=$(shell find org/opentreeoflife -name "*.java")

# ----- Targets

all: ott

# Shorthand target
compile: $(CLASS)

# Compile the Java classes
$(CLASS): $(JAVASOURCES) \
	  lib/jython-standalone-2.7.0.jar \
	  lib/json-simple-1.1.1.jar \
	  lib/junit-4.12.jar
	javac -g $(CP) $(JAVASOURCES)

# Script to start up jython (with OTT classes preloaded)
bin/jython:
	mkdir -p bin
	(echo "#!/bin/bash"; \
	 echo "export JYTHONPATH=.:$$PWD:$$PWD/util:$$PWD/lib/json-simple-1.1.1.jar"; \
	 echo exec java "$(JAVAFLAGS)" -jar $$PWD/lib/jython-standalone-2.7.0.jar '$$*') >$@
	chmod +x $@

# Script to start up the background daemon
bin/smasher:
	mkdir -p bin
	(echo "#!/bin/bash"; \
	 echo "cd $$PWD/service"; \
	 echo ./service '$$*') >$@
	chmod +x $@

# The open tree taxonomy

ott: tax/ott/log.tsv
tax/ott/log.tsv: $(CLASS) make-ott.py assemble_ott.py taxonomies.py \
                    tax/silva/taxonomy.tsv \
		    tax/fung/taxonomy.tsv tax/713/taxonomy.tsv \
		    tax/ncbi/taxonomy.tsv tax/gbif/taxonomy.tsv \
		    tax/irmng/taxonomy.tsv \
		    tax/worms/taxonomy.tsv \
		    feed/ott/edits/ott_edits.tsv \
		    tax/prev_ott/taxonomy.tsv \
		    feed/misc/chromista_spreadsheet.py \
		    ids_that_are_otus.tsv \
		    bin/jython \
		    inclusions.csv
	@rm -f *py.class
	@mkdir -p tax/ott
	time bin/jython make-ott.py
	echo $(WHICH) >tax/ott/version.txt

# ----- Taxonomy inputs

# Input: Index Fungorum

fung: tax/fung/taxonomy.tsv tax/fung/synonyms.tsv

tax/fung/taxonomy.tsv: 
	@mkdir -p tmp
	wget --output-document=tmp/fung-ot.tgz $@ $(FUNG_URL)
	(cd tmp; tar xzf fung-ot.tgz)
	@mkdir -p `dirname $@`
	mv tmp/fung*/* `dirname $@`/
	@ls -l $@

tax/fung/about.json:
	@mkdir -p `dirname $@`
	cp -p feed/fung/about.json tax/fung/

# Input: NCBI Taxonomy
# Formerly, where we now have /dev/null, we had
# ../data/ncbi/ncbi.taxonomy.homonym.ids.MANUAL_KEEP

ncbi: tax/ncbi/taxonomy.tsv
tax/ncbi/taxonomy.tsv: feed/ncbi/in/nodes.dmp feed/ncbi/process_ncbi_taxonomy_taxdump.py 
	@mkdir -p tax/ncbi.tmp
	@mkdir -p feed/ncbi/in
	python feed/ncbi/process_ncbi_taxonomy_taxdump.py F feed/ncbi/in \
            /dev/null tax/ncbi.tmp $(NCBI_URL)
	rm -rf tax/ncbi
	mv -f tax/ncbi.tmp tax/ncbi

feed/ncbi/in/nodes.dmp: feed/ncbi/in/taxdump.tar.gz
	@mkdir -p `dirname $@`
	tar -C feed/ncbi/in -xzvf feed/ncbi/in/taxdump.tar.gz
	touch $@

feed/ncbi/in/taxdump.tar.gz:
	@mkdir -p feed/ncbi/in
	wget --output-document=$@.new $(NCBI_URL)
	mv $@.new $@
	@ls -l $@

NCBI_ORIGIN_URL=ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz

refresh-ncbi:
	@mkdir -p feed/ncbi/in
	wget --output-document=feed/ncbi/in/taxdump.tar.gz.new $(NCBI_ORIGIN_URL)
	mv $@.new $@
	@ls -l $@

# Formerly, where it says /dev/null, we had ../data/gbif/ignore.txt

gbif: tax/gbif/taxonomy.tsv
tax/gbif/taxonomy.tsv: feed/gbif/in/taxon.txt feed/gbif/process_gbif_taxonomy.py
	@mkdir -p tax/gbif.tmp
	python feed/gbif/process_gbif_taxonomy.py \
	       feed/gbif/in/taxon.txt \
	       /dev/null tax/gbif.tmp
	cp -p feed/gbif/about.json tax/gbif.tmp/
	rm -rf tax/gbif
	mv -f tax/gbif.tmp tax/gbif

# The '|| true' is because unzip erroneously returns status code 1
# when there are warnings.
feed/gbif/in/taxon.txt: feed/gbif/in/checklist1.zip
	(cd feed/gbif/in && (unzip checklist1.zip || true))
	touch feed/gbif/in/taxon.txt

feed/gbif/in/checklist1.zip:
	@mkdir -p feed/gbif/in
	wget --output-document=$@.new "$(GBIF_URL)"
	mv $@.new $@
	@ls -l $@

GBIF_SOURCE_URL=http://rs.gbif.org/datasets/backbone/backbone-current.zip

refresh-gbif:
	@mkdir -p feed/gbif/in
	wget --output-document=$@.new "$(GBIF_SOURCE_URL)"
	mv $@.new $@
	@ls -l $@

# Input: WoRMS
# This is assembled by feed/worms/process_worms.py which does a web crawl

tax/worms/taxonomy.tsv:
	@mkdir -p tax/worms tmp
	wget --output-document=tmp/worms-1-ot.tgz $(WORMS_URL)
	(cd tmp; tar xzf worms-1-ot.tgz)
	rm -f tax/worms/*
	mv tmp/worms-1-ot*/* tax/worms/

# Input: IRMNG

irmng: tax/irmng/taxonomy.tsv

tax/irmng/taxonomy.tsv:
	@mkdir -p tax/irmng tmp/x
	wget --output-document=tmp/irmng-ot.tgz $(IRMNG_URL)
	(cd tmp/x; tar xzf ../irmng-ot.tgz)
	(x=`cd tmp/x; ls` && \
	 rm -rf tax/irmng tax/$$x && \
	 mv -f tmp/x/$$x tax/ && \
	 cd tax; ln -sf $$x irmng)

# Build IRMNG from Tony's .csv files - these files unfortunately are
# not public

refresh-irmng: feed/irmng/process_irmng.py feed/irmng/in/IRMNG_DWC.csv 
	@mkdir -p feed/irmng/out
	python feed/irmng/process_irmng.py \
	   feed/irmng/in/IRMNG_DWC.csv \
	   feed/irmng/in/IRMNG_DWC_SP_PROFILE.csv \
	   feed/irmng/out/taxonomy.tsv \
	   feed/irmng/out/synonyms.tsv
	rm -rf tax/irmng
	mv feed/irmng/out tax/irmng

feed/irmng/in/IRMNG_DWC.csv: feed/irmng/in/IRMNG_DWC.zip
	(cd feed/irmng/in && \
	 unzip IRMNG_DWC.zip && \
	 mv IRMNG_DWC_2???????.csv IRMNG_DWC.csv && \
	 mv IRMNG_DWC_SP_PROFILE_2???????.csv IRMNG_DWC_SP_PROFILE.csv)

feed/irmng/in/IRMNG_DWC.zip:
	@mkdir -p `dirname $@`
	wget --output-document=$@.new "http://www.cmar.csiro.au/datacentre/downloads/IRMNG_DWC.zip"
	mv $@.new $@

irmng-tarball:
	(mkdir -p $(TARDIR) && \
	 d=`date "+%Y%m%d"` && \
	 echo Today is $$d && \
	 cp -prf tax/irmng tax/irmng-ot-$$d && \
	 tar czvf $(TARDIR)/irmng-ot-$$d.tgz.tmp -C tax irmng-ot-$$d && \
	 mv $(TARDIR)/irmng-ot-$$d.tgz.tmp $(TARDIR)/irmng-ot-$$d.tgz )

publish-irmng:
	bin/publish-taxonomy irmng-ot


# Input: SILVA
# Significant tabs !!!

feed/silva/out/taxonomy.tsv: feed/silva/process_silva.py feed/silva/work/silva_no_sequences.fasta feed/silva/work/accessions.tsv 
	@mkdir -p feed/silva/out
	python feed/silva/process_silva.py \
	       feed/silva/work/silva_no_sequences.fasta \
	       feed/silva/work/accessions.tsv \
	       feed/silva/out "$(SILVA_URL)"

silva: $(SILVA)/taxonomy.tsv

$(SILVA)/taxonomy.tsv: feed/silva/out/taxonomy.tsv
	@mkdir -p $(SILVA)
	cp -p feed/silva/out/taxonomy.tsv $(SILVA)/
	cp -p feed/silva/out/synonyms.tsv $(SILVA)/
	cp -p feed/silva/out/about.json $(SILVA)/

feed/silva/in/silva.fasta:
	@mkdir -p `dirname $@`
	wget --output-document=$@.tgz.new "$(SILVA_URL)"
	mv $@.tgz.new $@.tgz
	@ls -l $@.tgz
	(cd feed/silva/in && tar xzvf silva.fasta.tgz && mv *silva.fasta silva.fasta)

# To make loading the information faster, we remove all the sequence data
feed/silva/work/silva_no_sequences.fasta: feed/silva/in/silva.fasta
	@mkdir -p feed/silva/work
	grep ">.*;" $< >$@.new
	mv $@.new $@

# This file has genbank id, ncbi id, strain, taxon name
feed/silva/work/accessions.tsv: feed/silva/work/silva_no_sequences.fasta \
				tax/ncbi/taxonomy.tsv \
				feed/silva/work/accessionid_to_taxonid.tsv
	python feed/silva/get_taxon_names.py \
	       tax/ncbi/taxonomy.tsv \
	       feed/silva/work/accessionid_to_taxonid.tsv \
	       $@.new
	mv $@.new $@

# No longer used

SILVA_RANKS_URL=$(SILVA_EXPORTS)/tax_ranks_ssu_115.csv
feed/silva/in/tax_ranks.txt:
	@mkdir -p `dirname $@`
	wget --output-document=$@.new $(SILVA_RANKS_URL)
	mv $@.new $@
	@ls -l $@

# ----- Katz lab Protista/Chromista parent assignments

z: feed/misc/chromista_spreadsheet.py
feed/misc/chromista_spreadsheet.py: feed/misc/chromista-spreadsheet.csv feed/misc/process_chromista_spreadsheet.py
	python feed/misc/process_chromista_spreadsheet.py \
           feed/misc/chromista-spreadsheet.csv >feed/misc/chromista_spreadsheet.py


# ----- Previous version of OTT, for id assignments

tax/prev_ott/taxonomy.tsv:
	@mkdir -p tmp 
	wget --output-document=tmp/prev_ott.tgz $(PREV_OTT_URL)
	@ls -l tmp/prev_ott.tgz
	(cd tmp/ && tar xvf prev_ott.tgz)
	rm -rf tax/prev_ott
	@mkdir -p tax/prev_ott
	mv tmp/ott*/* tax/prev_ott/
	if [ -e tax/prev_ott/taxonomy ]; then mv tax/prev_ott/taxonomy tax/prev_ott/taxonomy.tsv; fi
	if [ -e tax/prev_ott/synonyms ]; then mv tax/prev_ott/synonyms tax/prev_ott/synonyms.tsv; fi
	rm -rf tmp

# -----Taxon inclusion tests

# OK to override this locally, e.g. with
# ln -sf ../germinator/taxa/inclusions.tsv inclusions.tsv,
# so you can edit the file in the other repo.

inclusions.csv:
	wget --output-document=$@ --no-check-certificate \
	  "https://raw.githubusercontent.com/OpenTreeOfLife/germinator/master/taxa/inclusions.csv"

# ----- Preottol - for filling in the preottol id column
# No longer used
# PreOTToL is here if you're interested:
#  https://bitbucket.org/mtholder/ottol/src/dc0f89986c6c2a244b366312a76bae8c7be15742/preOTToL_20121112.txt?at=master
PREOTTOL=../../preottol

# Create the aux (preottol) mapping in a separate step.
# How does it know where to write to?

tax/ott/aux.tsv: $(CLASS) tax/ott/log.tsv
	$(JAVA) $(SMASH) tax/ott/ --aux $(PREOTTOL)/preottol-20121112.processed

$(PREOTTOL)/preottol-20121112.processed: $(PREOTTOL)/preOTToL_20121112.txt
	python util/process-preottol.py $< $@

# ----- Products

# For publishing OTT drafts or releases.

tarball: tax/ott/log.tsv
	(mkdir -p $(TARDIR) && \
	 tar czvf $(TARDIR)/ott$(WHICH).tgz.tmp -C tax ott \
	   --exclude differences.tsv && \
	 mv $(TARDIR)/ott$(WHICH).tgz.tmp $(TARDIR)/ott$(WHICH).tgz )
	@echo "Don't forget to bump the version number"

# Then, something like
# scp -p -i ~/.ssh/opentree/opentree.pem tarballs/ott2.9draft3.tgz \
#   opentree@ot10.opentreeoflife.org:files.opentreeoflife.org/ott/ott2.9/

# This rule typically won't run, since the target is checked in
ids_that_are_otus.tsv:
	time python util/ids_that_are_otus.py $@.new
	mv $@.new $@
	wc $@

# Not currently used since smasher already suppresses non-OTU deprecations
tax/ott/otu_deprecated.tsv: ids_that_are_otus.tsv tax/ott/deprecated.tsv
	$(JAVA) $(SMASH) --join ids_that_are_otus.tsv tax/ott/deprecated.tsv >$@.new
	mv $@.new $@
	wc $@

# This file is big
tax/ott/differences.tsv: tax/prev_ott/taxonomy.tsv tax/ott/taxonomy.tsv
	$(JAVA) $(SMASH) --diff tax/prev_ott/ tax/ott/ $@.new
	mv $@.new $@
	wc $@

# OTUs only
tax/ott/otu_differences.tsv: tax/ott/differences.tsv
	$(JAVA) $(SMASH) --join ids_that_are_otus.tsv tax/ott/differences.tsv >$@.new
	mv $@.new $@
	wc $@

tax/ott/otu_hidden.tsv: tax/ott/hidden.tsv
	$(JAVA) $(SMASH) --join ids_that_are_otus.tsv tax/ott/hidden.tsv >$@.new
	mv $@.new $@
	wc $@

# The works
works: ott tax/ott/otu_differences.tsv tax/ott/forwards.tsv

tags: $(JAVASOURCES)
	etags *.py util/*.py $(JAVASOURCES)

# ----- Libraries

lib/jython-standalone-2.7.0.jar:
	wget -O "$@" --no-check-certificate \
	 "http://search.maven.org/remotecontent?filepath=org/python/jython-standalone/2.7.0/jython-standalone-2.7.0.jar"
	@ls -l $@

lib/json-simple-1.1.1.jar:
	wget --output-document=$@ --no-check-certificate \
	  "https://json-simple.googlecode.com/files/json-simple-1.1.1.jar"
	@ls -l $@

lib/junit-4.12.jar:
	wget --output-document=$@ --no-check-certificate \
	  "http://search.maven.org/remotecontent?filepath=junit/junit/4.12/junit-4.12.jar"
	@ls -l $@

# ----- Testing

# Trivial, not very useful any more
test-smasher: compile
	$(JAVA) org.opentreeoflife.smasher.Test

# internal tests
test2: $(CLASS)
	$(JAVA) $(SMASH) --test

check:
	bash run-tests.sh

inclusion-tests: inclusions.csv 
	bin/jython util/check_inclusions.py inclusions.csv tax/ott/

# -----------------------------------------------------------------------------
# Asterales test system ('make test')

TAXON=Asterales

# t/tax/prev/taxonomy.tsv: tax/prev_ott/taxonomy.tsv   - correct expensive
t/tax/prev_aster/taxonomy.tsv: 
	@mkdir -p `dirname $@`
	$(JAVA) $(SMASH) tax/prev_ott/ --select2 $(TAXON) --out t/tax/prev_aster/

# dependency on tax/ncbi/taxonomy.tsv - correct expensive
t/tax/ncbi_aster/taxonomy.tsv: 
	@mkdir -p `dirname $@`
	$(JAVA) $(SMASH) tax/ncbi/ --select2 $(TAXON) --out t/tax/ncbi_aster/

# dependency on tax/gbif/taxonomy.tsv - correct but expensive
t/tax/gbif_aster/taxonomy.tsv: 
	@mkdir -p `dirname $@`
	$(JAVA) $(SMASH) tax/gbif/ --select2 $(TAXON) --out t/tax/gbif_aster/

# Previously:
#t/tax/aster/taxonomy.tsv: $(CLASS) \
#                          t/tax/ncbi_aster/taxonomy.tsv \
#                          t/tax/gbif_aster/taxonomy.tsv \
#                          t/tax/prev_aster/taxonomy.tsv \
#                          t/edits/edits.tsv
#        @mkdir -p `dirname $@`
#        $(JAVA) $(SMASH) t/tax/ncbi_aster/ t/tax/gbif_aster/ \
#             --edits t/edits/ \
#             --ids t/tax/prev_aster/ \
#             --out t/tax/aster/

# New:
t/tax/aster/taxonomy.tsv: compile t/aster.py \
                          t/tax/ncbi_aster/taxonomy.tsv \
                          t/tax/gbif_aster/taxonomy.tsv \
                          t/tax/prev_aster/taxonomy.tsv \
                          t/edits/edits.tsv \
			  bin/jython
	@mkdir -p `dirname $@`
	bin/jython t/aster.py

test: aster
aster: t/tax/aster/taxonomy.tsv

aster-tarball: t/tax/aster/taxonomy.tsv
	(mkdir -p $(TARDIR) && \
	 tar czvf $(TARDIR)/aster.tgz.tmp -C t/tax aster && \
	 mv $(TARDIR)/aster.tgz.tmp $(TARDIR)/aster.tgz )

# ----- Clean

clean:
	rm -rf feed/*/out
	rm -rf tax/fung tax/ncbi tax/prev_nem tax/silva
	rm -f $(CLASS)
#	rm -f feed/ncbi/in/taxdump.tar.gz

