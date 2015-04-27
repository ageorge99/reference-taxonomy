# Jython script to build the Open Tree reference taxonomy
# coding=utf-8

# Unless specified otherwise issues are in the reference-taxonomy repo:
# https://github.com/OpenTreeOfLife/reference-taxonomy/issues/...

import sys

from org.opentreeoflife.smasher import Taxonomy
import taxonomies
sys.path.append("feed/misc/")
from chromista_spreadsheet import fixChromista

ott = Taxonomy.newTaxonomy()
skel = Taxonomy.getTaxonomy('tax/skel/', 'skel')
ott.setSkeleton(skel)

# ----- SILVA microbial taxonomy -----
def prepare_silva():

    silva = taxonomies.loadSilva()

    # - Deal with parent/child homonyms in SILVA -
    # Arbitrary choices here to eliminate ambiguities down the road when NCBI gets merged.
    # (If the homonym is retained, then the merge algorithm will have no
    # way to choose between them, and refuse to match either.  It will
    # then create a third homonym.)
    # Note order dependence between the following two
    silva.taxon('Intramacronucleata','Intramacronucleata').rename('Intramacronucleata inf.')
    silva.taxon('Spirotrichea','Intramacronucleata inf.').rename('Spirotrichea inf.')
    silva.taxon('Cyanobacteria','Bacteria').rename('Cyanobacteria sup.')
    silva.taxon('Actinobacteria','Bacteria').rename('Actinobacteria sup.')
    silva.taxon('Acidobacteria','Bacteria').rename('Acidobacteria sup.')
    silva.taxon('Ochromonas','Ochromonadales').rename('Ochromonas sup.')
    silva.taxon('Tetrasphaera','Tetrasphaera').rename('Tetrasphaera inf.')

    # SILVA's placement of Rozella as a sibling of Fungi is contradicted
    # by Hibbett 2007, which puts it under Fungi.  Hibbett gets priority.
    # We make the change to SILVA to prevent Nucletmycea from being
    # labeled 'tattered'.
    silva.taxon('Fungi').take(silva.taxon('Rozella'))

    # 2014-04-12 Rick Ree #58 and #48 - make them match NCBI
    silva.taxon('Arthrobacter Sp. PF2M5').rename('Arthrobacter sp. PF2M5')
    silva.taxon('Halolamina sp. wsy15-h1').rename('Halolamina sp. WSY15-H1')
    # RR #55 - this is a silva/ncbi homonym
    silva.taxon('vesicomya').rename('Vesicomya')

    # From Laura and Dail on 5 Feb 2014
    # https://groups.google.com/forum/#!topic/opentreeoflife/a69fdC-N6pY
    silva.taxon('Diatomea').rename('Bacillariophyta')

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/30
    # https://github.com/OpenTreeOfLife/feedback/issues/5
    for name in ['GAL08', 'GOUTA4', 'JL-ETNP-Z39', 'Kazan-3B-28',
                 'LD1-PA38', 'MVP-21', 'NPL-UPA2', 'OC31', 'RsaHF231',
                 'S2R-29', 'SBYG-2791', 'SM2F11', 'WCHB1-60', 'T58',
                 'LKM74', 'LEMD255', 'CV1-B1-93', 'H1-10', 'H26-1',
                 'M1-18D08', 'D4P07G08', 'DH147-EKD10', 'LG25-05',
                 'NAMAKO-1', 'RT5iin25', 'SA1-3C06', 'DH147-EKD23']:
            silva.taxon(name).elide()  #maybe just hide instead ?

    # - Deal with division alignment issues -
    # In SILVA, Ctenophora is a genus inside of SAR, not a metazoan phylum
    if False:
            # *** The following seems to not work. ***
            ott.notSame(silva.taxon('Ctenophora', 'Coscinodiscophytina'),
                        skel.taxon('Ctenophora'))
    else:
        silva.taxon('Ctenophora', 'Coscinodiscophytina').prune()

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/79
    Ml = silva.taxon('Melampsora lini')
    if Ml != None: Ml.prune()
    Ps = silva.taxon('Polyangium sorediatum')
    if Ps != None: Ps.prune()
    up = silva.taxon('unidentified plasmid')
    if up != None: up.prune()

    ott.markDivisions(silva)
    taxonomies.checkDivisions(silva)
    return silva

silva = prepare_silva()

ott.absorb(silva)

# ----- Hibbett 2007 updated upper fungal taxonomy -----

def doH2007():
    h2007 = taxonomies.loadH2007()
    ott.absorb(h2007)
    # h2007/if synonym https://github.com/OpenTreeOfLife/reference-taxonomy/issues/40
    ott.taxon('Urocystales').synonym('Urocystidales')
    return h2007

h2007 = doH2007()

# ----- Index Fungorum -----
# IF is pretty comprehensive for Fungi, but has an assortment of other
# things, mostly eukaryotic microbes.  We should treat the former as
# more authoritative than NCBI, and the latter as less authoritative
# than NCBI.

def prepare_fungorum():

    fung  = taxonomies.loadFung()

    print "Index Fungorum has %s nodes"%fung.count()

    # analyzeMajorRankConflicts sets the "major_rank_conflict" flag when
    # intermediate ranks are missing (e.g. a family that's a child of a
    # class)
    fung.analyzeMajorRankConflicts()

    # JAR 2014-04-27 JAR found while investigating 'hidden' status of
    # Thelohania butleri.  Move out of Protozoa to prevent their being hidden
    # --- this seems to have been fixed in the 2014-04 version of IF
    # fung.taxon('Fungi').take(fung.taxon('Microsporidia'))

    # *** Non-Fungi processing

    # JAR 2014-05-13 Chlorophyte or fungus?  This one is very confused.
    # Pick it up from GBIF if at all
    # Mycobank and EOL (via Mycobank) put in in Algae
    # IF says it's a chlorophyte, not a fungus
    # First Nature says it's a synonym for a fungus (Terana caerulea) 'Cobalt crust fungus'
    # GBIF puts it in Basidiomycota (Fungi), synonym for Terana caerulea, in Phanerochaetaceae
    # Study pg_391 puts it sister to Phlebiopsis gigantea, in Basidiomycota
    # Study pg_1744 puts it sister to genus Phanerochaete, which is in Basidiomycota
    # Study pg_1160 puts is close to Phanerochaete and Hyphodermella
    # I'm thinking of putting it in Phanerochaetaceae. - GBIF does this for us.
    fung.taxon('Byssus phosphorea').prune()

    if False:  # see taxonomies.loadFung
        # Work in progress.  By promoting to root we've lost the fact that
        # protozoa are eukaryotes, which is unfortunate.  Not important in this
        # case, but suggestive of deeper problems in the framework.
        # Test case: Oomycota should end up in Stramenopiles.
        fung_Protozoa = fung.maybeTaxon('Protozoa')
        if fung_Protozoa != None:
            fung_Protozoa.hide()   # recursive
            fung_Protozoa.detach()
            fung_Protozoa.elide()
        fung_Chromista = fung.maybeTaxon('Chromista')
        if fung_Chromista != None:
            fung_Chromista.hide()  # recursive
            fung_Chromista.detach()
            fung_Chromista.elide()

    # IF Thraustochytriidae = SILVA Thraustochytriaceae ?  (Stramenopiles)
    # IF T. 90638 contains Sicyoidochytrium, Schizochytrium, Ulkenia, Thraustochytrium
    #  Parietichytrium, Elina, Botryochytrium, Althornia
    # SILVA T. contains Ulkenia and a few others of these... I say yes.
    thraust = fung.taxon('90377')
    thraust.synonym('Thraustochytriaceae')
    thraust.synonym('Thraustochytriidae')
    thraust.synonym('Thraustochytridae')

    # IF Labyrinthulaceae = SILVA Labyrinthulomycetes ?  NO.
    # IF L. contains only Labyrinthomyxa, Labyrinthula
    # SILVA L. contains a lot more than that.

    # IF Hyphochytriaceae = SILVA Hyphochytriales ?
    # SILVA Hyphochytriales = AB622284/#4 contains only
    # Hypochitrium, Rhizidiomycetaceae

    # There are two Bacillaria.
    # 1. NCBI 3002, in Stramenopiles, contains Bacillaria paxillifer.
    #    No synonyms in NCBI.
    #    IF has Bacillaria as a synonym for Camillea (if:777).
    #    Bacillaria is not otherwise in IF.
    #    Cammillea in IF is in Stramenopiles.
    # 2. NCBI 109369, in Pezizomycotina
    #    No synonyms in NCBI.
    # NCBI 13677 = Camillea, a fish.

    # There are two Polyangium, a bacterium (NCBI) and a flatworm (IF).

    # smush folds sibling taxa that have the same name.
    # (repeats - see loadFung()  ???)
    fung.smush()

    # *** Fungi processing

    print "Fungi in Index Fungorum has %s nodes"%fung.taxon('Fungi').count()

    # JAR 2014-04-11 Missing in earlier IF, mistake in later IF -
    # extraneous authority string.  See Romina's issue #42
    # This is a fungus.
    cyph = fung.maybeTaxon('Cyphellopsis')
    if cyph == None:
        cyph = fung.maybeTaxon('Cyphellopsis Donk 1931')
        if cyph != None:
            cyph.rename('Cyphellopsis')
        else:
            cyph = fung.newTaxon('Cyphellopsis', 'genus', 'if:17439')
        fung.taxon('Niaceae').take(cyph)

    # Romina 2014-04-09
    # IF has both Hypocrea and Trichoderma.  Hypocrea is the right name.
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/86
    fung.taxon('Trichoderma viride').rename('Hypocrea rufa')  # Type
    fung.taxon('Hypocrea').absorb(fung.taxonThatContains('Trichoderma', 'Hypocrea rufa'))

    # Romina https://github.com/OpenTreeOfLife/reference-taxonomy/issues/42
    fung.taxon('Trichoderma deliquescens').rename('Hypocrea lutea')

    # 2014-04-13 Romina #40, #60
    for foo in [('Neozygitales', ['Neozygitaceae']),
                ('Asterinales', ['Asterinaceae']),
                ('Savoryellales', ['Savoryella', 'Ascotaiwania', 'Ascothailandia']), 
                ('Cladochytriales', ['Cladochytriaceae', 'Nowakowskiellaceae', 'Septochytriaceae', 'Endochytriaceae']),
                ('Jaapiales', ['Jaapiaceae']),
                ('Coniocybales', ['Coniocybaceae']),
                ('Hyaloraphidiales', ['Hyaloraphidiaceae']),
                ('Mytilinidiales', ['Mytilinidiaceae', 'Gloniaceae'])]:
        order = fung.maybeTaxon(foo[0])
        if order != None:
            for family in foo[1]:
                order.take(fung.taxon(family))
        else:
            print '*** Missing fungal order', foo[0]

    fung.taxon('Asterinales').synonym('Asteriniales')  #backward compatibility

    # ** No taxon found with this name: Nowakowskiellaceae
    # ** No taxon found with this name: Septochytriaceae
    # ** No taxon found with this name: Jaapiaceae
    # ** (null=if:81865 Rhizocarpaceae) is already a child of (null=h2007:212 Rhizocarpales)
    # ** No taxon found with this name: Hyaloraphidiaceae

    # Yan Wong https://github.com/OpenTreeOfLife/reference-taxonomy/issues/116
    fung.taxon('Mycosphaeroides').extinct()
    fung.taxon('Majasphaeridium').extinct()

    # *** Alignment to SILVA

    # 2014-03-07 Prevent a false match
    # https://groups.google.com/d/msg/opentreeoflife/5SAPDerun70/fRjA2M6z8tIJ
    # This is a fungus in Pezizomycotina
    ott.notSame(silva.taxon('Phaeosphaeria'), fung.taxon('Phaeosphaeria'))

    # 2014-04-08 This was causing Agaricaceae to be paraphyletic
    ott.notSame(silva.taxon('Morganella'), fung.taxon('Morganella'))

    # 2014-04-08 More IF/SILVA bad matches
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/63
    for name in ['Acantharia',             # in Pezizomycotina
                 'Bogoriella',             # in Pezizomycotina
                 'Steinia',                # in Pezizomycotina
                 'Epiphloea',              # in Pezizomycotina
                 'Campanella',             # in Agaricomycotina
                 'Lacrymaria',             # in Agaricomycotina
                 'Frankia',                # in Pezizomycotina / bacterium in SILVA
                 'Phialina',               # in Pezizomycotina
                 ]:
        ott.notSame(silva.taxon(name), fung.taxon(name))
    # Trichoderma harzianum, Sclerotinia homoeocarpa, Puccinia
    # triticina are removed from SILVA early
                 
    # 2014-04-25 JAR
    # There are three Bostrychias: a rhodophyte, a fungus, and a bird.
    # The fungus name is a synonym for Cytospora.
    if fung.maybeTaxon('Bostrychia', 'Ascomycota') != None:
        ott.notSame(silva.taxon('Bostrychia', 'Rhodophyceae'), fung.taxon('Bostrychia', 'Ascomycota'))

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/20
    # Problem: Chlamydotomus is an incertae sedis child of Fungi.  Need to
    # find a good home for it.
    #
    # Mycobank says Chlamydotomus beigelii = Trichosporon beigelii:
    # http://www.mycobank.org/BioloMICS.aspx?Link=T&TableKey=14682616000000067&Rec=35058&Fields=All
    #
    # IF says the basionym is Pleurococcus beigelii, and P. beigelii's current name
    # is Geotrichum beigelii.  IF says the type for Trichosporon is Trichosporon beigelii,
    # and that T. beigelii's current name is Trichosporum beigelii... with no synonymies...
    # So IF does not corroborate Mycobank.
    #
    # So we could consider absorbing Chlamydotomus into Trichosoporon.  But...
    #
    # Not sure about this.  beigelii has a sister, cellaris, that should move along
    # with it, but the name Trichosporon cellaris has never been published.
    # Cb = ott.taxon('Chlamydotomus beigelii')
    # Cb.rename('Trichosporon beigelii')
    # ott.taxon('Trichosporon').take(Cb)
    #
    # Just make it incertae sedis and put off dealing with it until someone cares...

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/79
    ott.notSame(silva.taxon('Podocystis', 'Stramenopiles'), fung.taxon('Podocystis', 'Fungi'))

    return fung

fungorum = prepare_fungorum()

fungi_root = fungorum.taxon('Fungi')
fungi = fungorum.select(fungi_root)
fungi_root.trim()
fungorum_sans_fungi = fungorum

ott.absorb(fungi)

# the non-Fungi from Index Fungorum get absorbed below

# ----- Lamiales taxonomy from study 713 -----
# http://dx.doi.org/10.1186/1471-2148-10-352
study713  = taxonomies.load713()
ott.notSame(study713.taxon('Buchnera'), silva.taxon('Buchnera'))
ott.absorb(study713)

# ----- WoRMS -----

def prepare_worms():
    worms = taxonomies.loadWorms()
    worms.taxon('Viruses').prune()

    # 2015-02-17 According to WoRMS web site.  Occurs in pg_1229
    worms.taxon('Scenedesmus communis').synonym('Scenedesmus caudata')

    # See NCBI
    worms.taxon('Millericrinida').extant()

    worms.smush()  # Gracilimesus gorbunovi, pg_1783

    return worms

worms = prepare_worms()

# Malacostraca instead of Decapoda because it's in the skeleton
mal = worms.taxon('Malacostraca')
malacostraca = worms.select(mal)
mal.trim()
worms_sans_malacostraca = worms

ott.absorb(malacostraca)

# ----- NCBI Taxonomy -----

def doNcbi():

    ncbi = taxonomies.loadNcbi()

    ncbi.taxon('Viruses').hide()

    # David Hibbett has requested that for Fungi, only Index Fungorum
    # should be seen.  Rather than delete the NCBI fungal taxa, we just
    # mark them 'hidden' so they can be suppressed downstream.  This
    # preserves the identifier assignments, which may have been used
    # somewhere.
    ncbi.taxon('Fungi').hideDescendantsToRank('species')

    # - Touch-up -

    # RR 2014-04-12 #49
    ncbi.taxon('leotiomyceta').rename('Leotiomyceta')

    # RR #53
    ncbi.taxon('White-sloanea').synonym('White-Sloanea')

    # RR #56
    ncbi.taxon('sordariomyceta').rename('Sordariomyceta')

    # RR #52
    ncbi.taxon('spinocalanus spinosus').rename('Spinocalanus spinosus')
    ncbi.taxon('spinocalanus angusticeps').rename('Spinocalanus angusticeps')

    # RR #59
    ncbi.taxon('candidate division SR1').rename('Candidate division SR1')
    ncbi.taxon('candidate division WS6').rename('Candidate division WS6')
    ncbi.taxon('candidate division BRC1').rename('Candidate division BRC1')
    ncbi.taxon('candidate division OP9').rename('Candidate division OP9')
    ncbi.taxon('candidate division JS1').rename('Candidate division JS1')

    # RR #51
    ncbi.taxon('Dendro-hypnum').synonym('Dendro-Hypnum')
    # RR #45
    ncbi.taxon('Cyrto-hypnum').synonym('Cyrto-Hypnum')
    # RR #54
    ncbi.taxon('Sciuro-hypnum').synonym('Sciuro-Hypnum')

    # RR 2014-04-12 #46
    ncbi.taxon('Pechuel-loeschea').synonym('Pechuel-Loeschea')

    # RR #50
    ncbi.taxon('Saxofridericia').synonym('Saxo-Fridericia')
    ncbi.taxon('Saxofridericia').synonym('Saxo-fridericia')

    # RR #57
    ncbi.taxon('Solms-laubachia').synonym('Solms-Laubachia')

    # Romina 2014-04-09
    # NCBI has both Hypocrea and Trichoderma.
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/86
    ncbi.taxon('Trichoderma viride').rename('Hypocrea rufa')  # Type
    ncbi.taxon('Hypocrea').absorb(ncbi.taxonThatContains('Trichoderma', 'Hypocrea rufa'))

    # Mark Holder https://github.com/OpenTreeOfLife/reference-taxonomy/issues/120
    ncbi.taxon('Cetartiodactyla').synonym('Artiodactyla')

    # - Alignment to OTT -

    #ott.same(ncbi.taxon('Cyanobacteria'), silva.taxon('D88288/#3'))
    ott.notSame(ncbi.taxon('Burkea'), fungorum.taxon('Burkea'))
    ott.notSame(ncbi.taxon('Coscinium'), fungorum.taxon('Coscinium'))
    ott.notSame(ncbi.taxon('Perezia'), fungorum.taxon('Perezia'))

    # JAR 2014-04-11 Discovered during regression testing
    ott.notSame(ncbi.taxon('Epiphloea', 'Rhodophyta'), fungorum.taxon('Epiphloea', 'Ascomycota'))

    # JAR attempt to resolve ambiguous alignment of Trichosporon in IF and
    # NCBI based on common parent and member.
    # Type = T. beigelii, which is current, according to Mycobank.
    # But I'm going to use a different 'type', Trichosporon cutaneum.
    ott.same(fungorum.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'),
             #ncbi.taxonThatContains('Trichosporon', 'Trichosporon cutaneum')
             ncbi.taxon('5552')
             )

    # 2014-04-23 In new version of IF - obvious misalignment
    ott.notSame(ncbi.taxon('Crepidula', 'Gastropoda'), fungorum.taxon('Crepidula', 'Microsporidia'))
    ott.notSame(ncbi.taxon('Hessea', 'Viridiplantae'), fungorum.taxon('Hessea', 'Microsporidia'))
    # 2014-04-23 Resolve ambiguity introduced into new version of IF
    # http://www.speciesfungorum.org/Names/SynSpecies.asp?RecordID=331593
    ott.same(ncbi.taxon('Gymnopilus spectabilis var. junonius'), fungorum.taxon('Gymnopilus junonius'))

    # JAR 2014-04-23 More sample contamination in SILVA 115
    ott.same(ncbi.taxon('Lamprospora'), fungorum.taxon('Lamprospora'))

    # JAR 2014-04-25
    ott.notSame(silva.taxon('Bostrychia', 'Rhodophyceae'), ncbi.taxon('Bostrychia', 'Aves'))

    ott.absorb(ncbi)
    return ncbi

ncbi = doNcbi()

# 2014-01-27 Joseph: Quiscalus is incorrectly in
# Fringillidae instead of Icteridae.  NCBI is wrong, GBIF is correct.
# https://github.com/OpenTreeOfLife/reference-taxonomy/issues/87
ott.taxon('Icteridae').take(ott.taxon('Quiscalus', 'Fringillidae'))

# Misspelling in GBIF... seems to already be known
# Stephen email to JAR 2014-01-26
# ott.taxon("Torricelliaceae").synonym("Toricelliaceae")


print "Fungi in h2007 + if + ncbi has %s nodes"%ott.taxon('Fungi').count()

# ----- Non-decapods from WoRMS -----

ott.absorb(worms_sans_malacostraca)

# ----- Non-Fungi from Index Fungorum -----

ott.absorb(fungorum_sans_fungi)

# ----- GBIF (Global Biodiversity Information Facility) taxonomy -----

def doGbif():

    gbif = taxonomies.loadGbif()

    gbif.taxon('Viruses').hide()

    # Fungi suppressed at David Hibbett's request
    gbif.taxon('Fungi').hideDescendantsToRank('species')

    # Microbes suppressed at Laura Katz's request
    gbif.taxon('Bacteria','life').hideDescendants()
    gbif.taxon('Archaea','life').hideDescendants()

    # Paraphyletic - now taken care of in loadGbif
    if False:
        gbif_Protozoa = gbif.taxon('Protozoa')
        gbif_Protozoa.hide()   # recursive
        if False:
            gbif_Protozoa.detach()
            gbif_Protozoa.elide()
        gbif_Chromista = gbif.taxon('Chromista')
        gbif_Chromista.hide()   # recursive
        if False:
            gbif_Chromista.detach()
            gbif_Chromista.elide()

    # - Touch-up -

    # Rod Page blogged about this one
    # http://iphylo.blogspot.com/2014/03/gbif-liverwort-taxonomy-broken.html
    gbif.taxon('Jungermanniales','Marchantiophyta').absorb(gbif.taxon('Jungermanniales','Bryophyta'))

    # Joseph 2013-07-23 https://github.com/OpenTreeOfLife/opentree/issues/62
    # GBIF has two copies of Myospalax
    gbif.taxon('6006429').absorb(gbif.taxon('2439119'))

    # RR 2014-04-12 #47
    gbif.taxon('Drake-brockmania').absorb(gbif.taxon('Drake-Brockmania'))
    # RR #50 - this one is in NCBI, see above
    gbif.taxon('Saxofridericia').absorb(gbif.taxon('4930834')) #Saxo-Fridericia
    # RR #57 - the genus is in NCBI, see above
    gbif.taxon('Solms-laubachia').absorb(gbif.taxon('4908941')) #Solms-Laubachia
    gbif.taxon('Solms-laubachia pulcherrima').absorb(gbif.taxon('Solms-Laubachia pulcherrima'))

    # RR #45
    gbif.taxon('Cyrto-hypnum').absorb(gbif.taxon('4907605'))

    # 2014-04-13 JAR noticed while grepping
    gbif.taxon('Chryso-hypnum').absorb(gbif.taxon('Chryso-Hypnum'))
    gbif.taxon('Drepano-Hypnum').rename('Drepano-hypnum')
    gbif.taxon('Complanato-Hypnum').rename('Complanato-hypnum')
    gbif.taxon('Leptorrhyncho-Hypnum').rename('Leptorrhyncho-hypnum')

    # Romina 2014-04-09
    # GBIF has both Hypocrea and Trichoderma.  And it has four Trichoderma synonyms...
    # pick the one that contains bogo-type Hypocrea rufa
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/86
    gbif.taxon('Trichoderma viride').rename('Hypocrea rufa')  # Type
    gbif.taxon('Hypocrea').absorb(gbif.taxonThatContains('Trichoderma', 'Hypocrea rufa'))

    # 2014-04-21 RR
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/45
    for epithet in ['cylindraceum',
                    'lepidoziaceum',
                    'intermedium',
                    'espinosae',
                    'pseudoinvolvens',
                    'arzobispoae',
                    'sharpii',
                    'frontinoae',
                    'atlanticum',
                    'stevensii',
                    'brachythecium']:
        gbif.taxon('Cyrto-hypnum ' + epithet).absorb(gbif.taxon('Cyrto-Hypnum ' + epithet))

    # JAR 2014-04-23 Noticed while perusing silva/gbif conflicts
    gbif.taxon('Ebriaceae').synonym('Ebriacea')
    gbif.taxon('Acanthocystidae').absorb(gbif.taxon('Acanthocistidae'))
    gbif.taxon('Dinophyta').synonym('Dinoflagellata')

    # JAR 2014-06-29 stumbled on this while trying out new alignment
    # methods and examining troublesome homonym Bullacta exarata.
    # GBIF obviously puts it in the wrong place, see description at
    # http://www.gbif.org/species/4599744 (it's a snail, not a shrimp).
    bex = gbif.taxon('Bullacta exarata', 'Atyidae')
    bec = gbif.taxon('Bullacta ecarata', 'Atyidae')
    if bex != None and bec != None:
        bex.absorb(bec)
        bex.detach()

    # Yan Wong 2014-12-16 https://github.com/OpenTreeOfLife/reference-taxonomy/issues/116
    for name in ['Griphopithecus', 'Asiadapis',
                 'Lomorupithecus', 'Marcgodinotius', 'Muangthanhinius',
                 'Plesiopithecus', 'Suratius', 'Killikaike blakei', 'Rissoina bonneti']:
        gbif.taxon(name).extinct()

    # Doug Soltis 2015-02-17 https://github.com/OpenTreeOfLife/feedback/issues/59 
    # http://dx.doi.org/10.1016/0034-6667(95)00105-0
    gbif.taxon('Timothyia').extinct()

    # - Alignment -

    #ott.same(gbif.taxon('Cyanobacteria'), silva.taxon('Cyanobacteria','Cyanobacteria')) #'D88288/#3'

    # Automatic alignment makes the wrong choice for the following two
    ott.same(ncbi.taxon('5878'), gbif.taxon('10'))    # Ciliophora gbif:3269382
    ott.same(ncbi.taxon('29178'), gbif.taxon('389'))  # Foraminifera gbif:4983431

    # Tetrasphaera is a messy multi-way homonym
    ott.same(ncbi.taxon('Tetrasphaera','Intrasporangiaceae'), gbif.taxon('Tetrasphaera','Intrasporangiaceae'))

    # SILVA's Retaria is in SAR, GBIF's is in Brachiopoda
    ott.notSame(silva.taxon('Retaria'), gbif.taxon('Retaria'))

    # Bad alignments to NCBI
    ott.notSame(ncbi.taxon('Labyrinthomorpha'), gbif.taxon('Labyrinthomorpha'))
    ott.notSame(ncbi.taxon('Ophiurina'), gbif.taxon('Ophiurina','Ophiurinidae'))
    ott.notSame(ncbi.taxon('Rhynchonelloidea'), gbif.taxon('Rhynchonelloidea'))
    ott.notSame(ncbi.taxon('Neoptera'), gbif.taxon('Neoptera', 'Diptera'))
    ott.notSame(gbif.taxon('6101461'), ncbi.taxon('Tipuloidea')) # genus Tipuloidea
    ott.notSame(silva.taxon('GN013951'), gbif.taxon('Gorkadinium')) #Tetrasphaera

    # Rick Ree 2014-03-28 https://github.com/OpenTreeOfLife/reference-taxonomy/issues/37
    ott.same(ncbi.taxon('Calothrix', 'Rivulariaceae'), gbif.taxon('Calothrix', 'Rivulariaceae'))
    ott.same(ncbi.taxon('Chlorella', 'Chlorellaceae'), gbif.taxon('Chlorella', 'Chlorellaceae'))
    ott.same(ncbi.taxon('Myrmecia', 'Microthamniales'), gbif.taxon('Myrmecia', 'Microthamniales'))

    # JAR 2014-04-18 attempt to resolve ambiguous alignment of
    # Trichosporon in IF and GBIF based on common member
    # ott.same(fungorum.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'),
    #          gbif.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))
    # doesn't work.  brute force.
    ott.same(fungorum.taxon('10296'), gbif.taxon('2518163'))

    # Obviously the same genus, can't tell what's going on
    ott.same(gbif.taxon('Hygrocybe'), fungorum.taxon('Hygrocybe'))

    # JAR 2014-04-23 More sample contamination in SILVA 115
    ott.same(gbif.taxon('Lamprospora'), fungorum.taxon('Lamprospora'))

    # JAR 2014-04-23 IF update fallout
    ott.same(gbif.taxonThatContains('Penicillium', 'Penicillium expansum'), fungorum.taxonThatContains('Penicillium', 'Penicillium expansum'))

    ott.absorb(gbif)
    return gbif

gbif = doGbif()

# Joseph 2014-01-27 https://code.google.com/p/gbif-ecat/issues/detail?id=104
ott.taxon('Parulidae').take(ott.taxon('Myiothlypis', 'Passeriformes'))
# I don't get why this one isn't a major_rank_conflict !? - bug. (so to speak.)
ott.taxon('Blattaria').take(ott.taxon('Phyllodromiidae'))


# ----- Interim Register of Marine and Nonmarine Genera (IRMNG) -----

def doIrmng():

    irmng = taxonomies.loadIrmng()

    irmng.taxon('Viruses').hide()

    # Fungi suppressed at David Hibbett's request
    irmng.taxon('Fungi').hideDescendantsToRank('species')

    # Neopithecus (extinct) occurs in two places.  Flush one, mark the other
    irmng.taxon('1413316').prune() #Neopithecus in Mammalia
    irmng.taxon('1413315').extinct() #Neopithecus in Primates (Pongidae)

    ott.same(gbif.taxon('3172047'), irmng.taxon('1381293'))  # Veronica
    ott.same(gbif.taxon('6101461'), irmng.taxon('1170022')) # genus Tipuloidea (not superfamily)
    # IRMNG has four Tetrasphaeras.
    ott.same(ncbi.taxon('Tetrasphaera','Intrasporangiaceae'), irmng.taxon('Tetrasphaera','Intrasporangiaceae'))
    ott.same(gbif.taxon('Gorkadinium','Dinophyceae'), irmng.taxon('Gorkadinium','Dinophyceae'))

    # Microbes suppressed at Laura Katz's request
    irmng.taxon('Bacteria','life').hideDescendants()
    irmng.taxon('Archaea','life').hideDescendants()

    # RR #50
    # irmng.taxon('Saxo-Fridericia').rename('Saxofridericia')
    # irmng.taxon('Saxofridericia').absorb(irmng.taxon('Saxo-fridericia'))
    saxo = irmng.maybeTaxon('1063899')
    if saxo != None:
        saxo.absorb(irmng.taxon('1071613'))

    # Romina 2014-04-09
    # IRMNG has EIGHT different Trichodermas.  (Four are synonyms of other things.)
    # 1307461 = Trichoderma Persoon 1794, in Hypocreaceae
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/86
    irmng.taxon('Hypocrea').absorb(irmng.taxon('1307461'))

    # JAR 2014-04-18 attempt to resolve ambiguous alignment of
    # Trichosporon in IF and IRMNG based on common parent and member
    ott.same(fungorum.taxon('Trichosporon'), irmng.taxon('Trichosporon'))

    # JAR 2014-04-24 false match
    ott.notSame(irmng.taxon('Protaspis', 'Chordata'), ncbi.taxon('Protaspis', 'Cercozoa'))

    # JAR 2014-04-18 while investigating hidden status of Coscinodiscus radiatus
    ott.notSame(irmng.taxon('Coscinodiscus', 'Porifera'), ncbi.taxon('Coscinodiscus', 'Stramenopiles'))

    # Protista is paraphyletic
    if False:
        irmng_Protista = irmng.taxon('Protista','life')
        irmng_Protista.hide()
        if False:
            irmng_Protista.detach()
            irmng_Protista.elide()

    ott.absorb(irmng)
    return irmng

irmng = doIrmng()

# ----- Final patches -----

# Finished loading source taxonomies.  Now patch things up.

def patch_ott():

    # See above (occurs in both IF and GBIF).  Also see issue #67
    ott.taxon('Chlamydotomus').incertaeSedis()

    # Joseph Brown 2014-01-27
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/87
    ott.taxon('Thamnophilus bernardi').absorb(ott.taxon('Sakesphorus bernardi'))
    ott.taxon('Thamnophilus melanonotus').absorb(ott.taxon('Sakesphorus melanonotus'))
    ott.taxon('Thamnophilus melanothorax').absorb(ott.taxon('Sakesphorus melanothorax'))
    ott.taxon('Thamnophilus bernardi').synonym('Sakesphorus bernardi')
    ott.taxon('Thamnophilus melanonotus').synonym('Sakesphorus melanonotus')
    ott.taxon('Thamnophilus melanothorax').synonym('Sakesphorus melanothorax')

    # Mammals - groups cluttering basal part of tree
    ott.taxon('Litopterna').extinct()
    ott.taxon('Notoungulata').extinct()
    # Artiodactyls
    ott.taxon('Boreameryx').extinct()
    ott.taxon('Thandaungia').extinct()
    ott.taxon('Limeryx').extinct()
    ott.taxon('Delahomeryx').extinct()
    ott.taxon('Krabitherium').extinct()
    ott.taxon('Discritochoerus').extinct()
    ott.taxon('Brachyhyops').extinct()

    # Not fungi - Romina 2014-01-28
    # ott.taxon('Adlerocystis').show()  - it's Chromista ...
    # Index Fungorum says Adlerocystis is Chromista, but I don't believe it
    # ott.taxon('Chromista').take(ott.taxon('Adlerocystis','Fungi'))

    # Adlerocystis seems to be a fungus, but unclassified - JAR 2014-03-10
    ott.taxon('Adlerocystis').incertaeSedis()

    # "No clear identity has emerged"
    #  http://forestis.rsvs.ulaval.ca/REFERENCES_X/phylogeny.arizona.edu/tree/eukaryotes/accessory/parasitic.html
    # Need to hide it because it clutters base of Fungi
    ott.taxon('Amylophagus','Fungi').incertaeSedis()

    # Bad synonym - Tony Rees 2014-01-28
    # https://groups.google.com/d/msg/opentreeoflife/SrI7KpPgoPQ/ihooRUSayXkJ
    ott.taxon('Lemania pluvialis').prune()

    # Tony Rees 2014-01-29
    # https://groups.google.com/d/msg/opentreeoflife/SrI7KpPgoPQ/wTeD17GzOGoJ
    trigo = ott.maybeTaxon('Trigonocarpales')
    if trigo != None: trigo.extinct()

    #Pinophyta and daughters need to be deleted; - Bryan 2014-01-28
    #Lycopsida and daughters need to be deleted;
    #Pteridophyta and daughters need to be deleted;
    #Gymnospermophyta and daughters need to be deleted;
    ott.taxon('Pinophyta','Chloroplastida').incertaeSedis()
    ott.taxon('Pteridophyta','Chloroplastida').incertaeSedis()
    ott.taxon('Gymnospermophyta','Chloroplastida').incertaeSedis()

    # Patches from the Katz lab to give decent parents to taxa classified
    # as Chromista or Protozoa
    print '-- Chromista/Protozoa spreadsheet from Katz lab --'
    fixChromista(ott)

    print '-- more patches --'

    # From Laura and Dail on 5 Feb 2014
    # https://groups.google.com/d/msg/opentreeoflife/a69fdC-N6pY/y9QLqdqACawJ
    ott.taxon('Chlamydiae/Verrucomicrobia group').rename('Verrucomicrobia group')
    ott.taxon('Heterolobosea','Discicristata').absorb(ott.taxon('Heterolobosea','Percolozoa'))
    ott.taxon('Excavata','Eukaryota').take(ott.taxon('Oxymonadida','Eukaryota'))

    # Work in progress - Joseph
    ott.taxon('Reptilia').hide()

    # Chris Owen patches 2014-01-30
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/88
    ott.taxon('Protostomia').take(ott.taxon('Chaetognatha','Deuterostomia'))
    ott.taxon('Lophotrochozoa').take(ott.taxon('Platyhelminthes'))
    ott.taxon('Polychaeta','Annelida').take(ott.taxon('Myzostomida'))
    ott.taxon('Lophotrochozoa').take(ott.taxon('Gnathostomulida'))
    ott.taxon('Bilateria').take(ott.taxon('Acoela'))
    ott.taxon('Bilateria').take(ott.taxon('Xenoturbella'))
    ott.taxon('Bilateria').take(ott.taxon('Nemertodermatida'))
    #  8) Stauromedusae should be a class (Staurozoa; Marques and Collins 2004) and should be removed from Scyphozoa
    ott.taxon('Cnidaria').take(ott.taxon('Stauromedusae'))
    ott.taxon('Copepoda').take(ott.taxon('Prionodiaptomus'))

    # Bryan Drew patches 2014-01-30 
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/89
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/90
    ott.taxon('Scapaniaceae').absorb(ott.taxon('Lophoziaceae'))
    ott.taxon('Salazaria mexicana').rename('Scutellaria mexicana')
    # One Scutellaria is in Lamiaceae; the other is a fungus.
    # IRMNG's Salazaria 1288740 is in Lamiales, and is a synonym of Scutellaria.
    ott.taxon('Scutellaria','Lamiaceae').absorb(ott.image(gbif.taxon('Salazaria')))
    sal = irmng.maybeTaxon('1288740')
    if sal != None:
        ott.taxon('Scutellaria','Lamiaceae').absorb(ott.image(sal)) #Salazaria

    #  Make an order Boraginales that contains Boraginaceae + Hydrophyllaceae
    #  http://dx.doi.org/10.1111/cla.12061
    # Bryan Drew 2013-09-30
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/91
    ott.taxon('Boraginaceae').absorb(ott.taxon('Hydrophyllaceae'))
    ott.taxon('Boraginales').take(ott.taxon('Boraginaceae'))
    ott.taxon('lamiids').take(ott.taxon('Boraginales'))

    # Bryan Drew 2014-01-30
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/90
    # Vahlia 26024 <- Vahliaceae 23372 <- lammids 596112 (was incertae sedis)
    ott.taxon('lamiids').take(ott.taxon('Vahliaceae'))

    # Bryan Drew 2014-01-30
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/90
    # http://www.sciencedirect.com/science/article/pii/S0034666703000927
    ott.taxon('Araripia').extinct()

    # Bryan Drew  2014-02-05
    # http://www.mobot.org/mobot/research/apweb/
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/92
    ott.taxon('Viscaceae').rename('Visceae')
    ott.taxon('Amphorogynaceae').rename('Amphorogyneae')
    ott.taxon('Thesiaceae').rename('Thesieae')
    ott.taxon('Santalaceae').take(ott.taxon('Visceae'))
    ott.taxon('Santalaceae').take(ott.taxon('Amphorogyneae'))
    ott.taxon('Santalaceae').take(ott.taxon('Thesieae'))
    ott.taxon('Santalaceae').absorb(ott.taxon('Cervantesiaceae'))
    ott.taxon('Santalaceae').absorb(ott.taxon('Comandraceae'))

    # Bryan Drew 2014-01-30
    # http://dx.doi.org/10.1126/science.282.5394.1692 
    ott.taxon('Magnoliophyta').take(ott.taxon('Archaefructus'))

    # Bryan Drew 2014-01-30
    # http://deepblue.lib.umich.edu/bitstream/handle/2027.42/48219/ID058.pdf
    ott.taxon('eudicotyledons').take(ott.taxon('Phyllites'))

    # Bryan Drew 2014-02-13
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/93
    # http://dx.doi.org/10.1007/978-3-540-31051-8_2
    ott.taxon('Alseuosmiaceae').take(ott.taxon('Platyspermation'))

    # JAR 2014-02-24.  We are getting extinctness information for genus
    # and above from IRMNG, but not for species.
    # There's a similar problem in Equus.
    for name in ['Homo sapiens neanderthalensis',
                 'Homo sapiens ssp. Denisova',
                 'Homo habilis',
                 'Homo erectus',
                 'Homo cepranensis',
                 'Homo georgicus',
                 'Homo floresiensis',
                 'Homo kenyaensis',
                 'Homo rudolfensis',
                 'Homo antecessor',
                 'Homo ergaster',
                 'Homo okotensis']:
        ott.taxon(name).extinct()

    # JAR 2014-03-07 hack to prevent H.s. from being extinct due to all of
    # its subspecies being extinct.
    # I wish I knew what the authority for the H.s.s. name was.
    hss = ott.newTaxon('Homo sapiens sapiens', 'subspecies', 'https://en.wikipedia.org/wiki/Homo_sapiens_sapiens')
    ott.taxon('Homo sapiens').take(hss)
    hss.hide()

    # Raised by Joseph Brown 2014-03-09, solution proposed by JAR
    # Tribolium is incertae sedis in NCBI but we want it to not be hidden,
    # since it's a model organism.
    # Placement in Tenebrioninae is according to http://bugguide.net/node/view/152 .
    # Is this cheating?
    ott.taxon('Tenebrioninae').take(ott.taxon('Tribolium','Coleoptera'))

    # Bryan Drew 2014-03-20 http://dx.doi.org/10.1186/1471-2148-14-23
    ott.taxon('Pentapetalae').take(ott.taxon('Vitales'))

    # Bryan Drew 2014-03-14 http://dx.doi.org/10.1186/1471-2148-14-23
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/24
    ott.taxon('Streptophytina').elide()

    # Dail 2014-03-20
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/29
    # Note misspelling in SILVA
    ott.taxon('Freshwayer Opisthokonta').rename('Freshwater Microbial Opisthokonta')

    # JAR 2014-03-31 just poking around
    # Many of these would be handled by major_rank_conflict if it worked
    # http://tolweb.org/tree?group=Temnospondyli
    ott.taxon('Temnospondyli').extinct()
    # https://en.wikipedia.org/wiki/Eobatrachus
    ott.taxon('Eobatrachus').extinct()
    # https://en.wikipedia.org/wiki/Vulcanobatrachus
    ott.taxon('Vulcanobatrachus').extinct()
    # https://en.wikipedia.org/wiki/Beelzebufo
    ott.taxon('Beelzebufo').extinct()
    # https://en.wikipedia.org/wiki/Iridotriton
    ott.taxon('Iridotriton').extinct()
    # https://en.wikipedia.org/wiki/Baurubatrachus
    ott.taxon('Baurubatrachus').extinct()

    # Dail 2014-03-31 https://github.com/OpenTreeOfLife/feedback/issues/5
    ott.taxon('Katablepharidophyta').hide()

    # Dail 2014-03-31 https://github.com/OpenTreeOfLife/feedback/issues/4
    # no evidence given
    ott.taxonThatContains('Bacteria', 'Lentisphaerae').take(ott.taxon('Lentisphaerae'))

    # David Hibbett 2014-04-02 misspelling in h2007 file
    # (Dacrymecetales is 'no rank', Dacrymycetes is a class)
    if ott.maybeTaxon('Dacrymecetales') != None:
        ott.taxon('Dacrymecetales').rename('Dacrymycetes')

    # Dail https://github.com/OpenTreeOfLife/feedback/issues/6
    ott.taxon('Telonema').synonym('Teleonema')

    # Joseph https://github.com/OpenTreeOfLife/reference-taxonomy/issues/43
    ott.taxon('Lorisiformes').take(ott.taxon('Lorisidae'))

    # Romina https://github.com/OpenTreeOfLife/reference-taxonomy/issues/42
    # As of 2014-04-23 IF synonymizes Cyphellopsis to Merismodes
    ott.taxon('Cyphellopsis','Cyphellaceae').unhide()
    if ott.maybeTaxon('Cyphellopsis','Niaceae') != None:
        ott.taxon('Cyphellopsis','Cyphellaceae').absorb(ott.taxon('Cyphellopsis','Niaceae'))

    ott.taxon('Diaporthaceae').take(ott.taxon('Phomopsis'))
    ott.taxon('Valsaceae').take(ott.taxon('Valsa', 'Fungi'))
    ott.taxon('Agaricaceae').take(ott.taxon('Cystoderma','Fungi'))
    # Invert the synonym relationship
    ott.taxon('Hypocrea lutea').absorb(ott.taxon('Trichoderma deliquescens'))

    # Fold Norops into Anolis
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/31
    # TBD: Change species names from Norops X to Anolis X for all X
    ott.taxon('Anolis').absorb(ott.taxon('Norops', 'Iguanidae'))

    # JAR 2014-04-08 - these are in study OTUs - see IRMNG
    ott.taxon('Inseliellum').extant()
    ott.taxon('Conus', 'Gastropoda').extant()
    ott.taxon('Patelloida').extant()
    ott.taxon('Phyllanthus', 'Phyllanthaceae').extant()
    ott.taxon('Stelis','Orchidaceae').extant()
    ott.taxon('Chloris', 'Poaceae').extant()
    ott.taxon('Acropora', 'Acroporidae').extant()
    ott.taxon('Diadasia').extant()

    # JAR 2014-04-24
    # grep "ncbi:.*extinct_inherited" tax/ott/taxonomy.tsv | head
    ott.taxon('Tarsius').extant()
    ott.taxon('Odontesthes').extant()
    ott.taxon('Leiognathus', 'Chordata').extant()
    ott.taxon('Oscheius').extant()
    ott.taxon('Cicindela').extant()
    ott.taxon('Leucothoe', 'Ericales').extant()
    ott.taxon('Hydrornis').extant()
    ott.taxon('Bostrychia harveyi').extant() #fungus
    ott.taxon('Agaricia').extant() #coral
    ott.taxon('Dischidia').extant() #eudicot

    # JAR 2014-04-26
    ott.taxon('Acritarcha').extinct()

    # JAR 2014-05-13
    ott.taxon('Saurischia').extant()
    # there are two of these, maybe should be merged.
    # ott.taxon('Myoxidae', 'Rodentia').extant()

    # JAR 2014-05-08 while looking at the deprecated ids file. 
    # http://www.theplantlist.org/tpl/record/kew-2674785
    ott.taxon('Berendtiella rugosa').synonym('Berendtia rugosa')

    # JAR 2014-05-13 These are marked extinct by IRMNG but are all in NCBI
    # and have necleotide sequences
    ott.taxon('Zemetallina').extant()
    ott.taxon('Nullibrotheas').extant()
    ott.taxon('Fissiphallius').extant()
    ott.taxon('Nullibrotheas').extant()
    ott.taxon('Sinelater').extant()
    ott.taxon('Phanerothecium').extant()
    ott.taxon('Cephalotaxaceae').extant()
    ott.taxon('Vittaria elongata').extant()
    ott.taxon('Neogymnocrinus').extant()

    # JAR 2014-05-13 weird problem
    # NCBI incorrectly has both Cycadidae and Cycadophyta as children of Acrogymnospermae.
    # Cycadophyta (class, with daughter Cycadopsida) has no sequences.
    # The net effect is a bunch of extinct IRMNG genera showing up in
    # Cycadophyta, with Cycadophyta entirely extinct.
    #
    # NCBI has subclass Cycadidae =                     order Cycadales
    # GBIF has phylum Cycadophyta = class Cycadopsida = order Cycadales
    # IRMNG has                     class Cycadopsida = order Cycadales
    if ott.maybeTaxon('Cycadidae') != None:
        ott.taxon('Cycadidae').absorb(ott.taxon('Cycadopsida'))
        ott.taxon('Cycadidae').absorb(ott.taxon('Cycadophyta'))

    # Similar problem with Gnetidae and Ginkgoidae

    # Dail 2014-03-31
    # https://github.com/OpenTreeOfLife/feedback/issues/6
    ott.taxon('Telonema').synonym('Teleonema')

    # JAR noticed 2015-02-17  used in pg_2460
    # http://reptile-database.reptarium.cz/species?genus=Parasuta&species=spectabilis
    ott.taxon('Parasuta spectabilis').synonym('Rhinoplocephalus spectabilis')

    # Bryan Drew 2015-02-17 http://dx.doi.org/10.1016/j.ympev.2014.11.011
    sax = ott.taxon('Saxifragella bicuspidata')
    ott.taxon('Saxifraga').take(sax)
    sax.rename('Saxifraga bicuspidata')

patch_ott()

# -----------------------------------------------------------------------------
# Finish up

# "Old" patch system
ott.edit('feed/ott/edits/')

# Assign OTT ids to all taxa, re-using old ids when possible
ids = Taxonomy.getTaxonomy('tax/prev_ott/')

# JAR manual intervention to preserve ids
# These OTUs came up as ambiguous. Keep old ids.
ott.same(ids.taxon('4107132'), fungorum.taxon('11060')) #Cryptococcus
ott.same(ids.taxon('339002'), ncbi.taxon('3071')) #Chlorella
ott.same(ids.taxon('342868'), ncbi.taxon('56708')) #Tetraphyllidea
ott.same(ids.taxon('772892'), ncbi.taxon('1883')) #Streptomyces

ott.same(fungorum.taxon('Trichosporon'), ids.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))

# JAR 2014-05-13
# NCBI renamed Escherichia coli DSM 30083 = JCM 1649 = ATCC 11775
# 67952 2542    Bifidobacterium pseudocatenulatum DSM 20438 = JCM 1200  ncbi:547043 ?       *
# 479261    2542    Bifidobacterium catenulatum DSM 16992 = JCM 1194    ncbi:566552 ?       *
# 613687    2448    Escherichia coli DSM 30083 = JCM 1649   ncbi:866789 ?       *
ott.same(ids.taxon('67952'), ncbi.taxon('547043')) 
ott.same(ids.taxon('479261'), ncbi.taxon('566552')) 
ott.same(ids.taxon('613687'), ncbi.taxon('866789')) 
# 4773  2319    Phytopythium montanum   ncbi:214887,gbif:5433822    ?       *
ott.same(ids.taxon('4773'), ncbi.taxon('214887'))
# 289517    227 Rinorea dimakoensis ncbi:317423 ?       *
ott.same(ids.taxon('289517'), ncbi.taxon('317423'))


ott.assignIds(ids)

# Remove all trees but the largest 
ott.deforestate()

ott.parentChildHomonymReport()

# Write files
ott.dump('tax/ott/')
