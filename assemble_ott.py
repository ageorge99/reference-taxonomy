# Jython script to build the Open Tree reference taxonomy
# coding=utf-8

# Unless specified otherwise issues are in the reference-taxonomy repo:
# https://github.com/OpenTreeOfLife/reference-taxonomy/issues/...

import sys

from org.opentreeoflife.taxa import Taxonomy, SourceTaxonomy, TsvEdits, Addition, Rank, Taxon
from org.opentreeoflife.smasher import UnionTaxonomy
import ncbi_ott_assignments
sys.path.append("feed/misc/")
from chromista_spreadsheet import fixChromista
import taxonomies
import check_inclusions
from establish import establish
from claim import *
import csv

this_source = 'https://github.com/OpenTreeOfLife/reference-taxonomy/blob/master/make-ott.py'
inclusions_path = 'inclusions.csv'
additions_clone_path = 'feed/amendments/amendments-1'
new_taxa_path = 'new_taxa'

do_notSames = False

# temporary debugging thing
invariants = [Has_child('Nucletmycea', 'Fungi'),
              Has_child('Opisthokonta', 'Nucletmycea'),
              #Has_child('Rhizobiales', 'Xanthobacteraceae'), # D11342/#4 parent of D11342/#5
]

def check_invariants(ott):
    test_claims(ott, invariants)

def create_ott():

    ott = UnionTaxonomy.newTaxonomy('ott')

    # There ought to be tests for all of these...

    for name in names_of_interest:
        ott.eventLogger.namesOfInterest.add(name)

    # When lumping, prefer to use ids that have been used in OTU matching
    # This list could be used for all sorts of purposes...
    ott.loadPreferredIds('ids_that_are_otus.tsv', False)
    ott.loadPreferredIds('ids_in_synthesis.tsv', True)

    # idspace string 'skel' is magical, see Taxon.addSource
    ott.setSkeleton(Taxonomy.getTaxonomy('tax/skel/', 'skel'))

    # This is a particularly hard case; create alignment targets up front
    deal_with_ctenophora(ott)

    # SILVA
    silva = taxonomies.load_silva()
    silva_to_ott = align_silva(silva, ott)
    ott.absorb(silva, silva_to_ott)
    check_invariants(ott)

    # Hibbett 2007
    h2007 = taxonomies.load_h2007()
    h2007_to_ott = ott.absorb(h2007)

    # Index Fungorum
    (fungi, fungorum_sans_fungi) = split_fungorum(ott)
    ott.absorb(fungi, align_fungi(fungi, ott))
    check_invariants(ott)

    # the non-Fungi from Index Fungorum get absorbed below

    lamiales = taxonomies.load_713()
    ott.absorb(lamiales, align_lamiales(lamiales, ott))

    # WoRMS
    # higher priority to Worms for Malacostraca, Cnidaria so we split out
    # those clades from worms and absorb them before NCBI
    worms = taxonomies.load_worms()
    # Malacostraca instead of Decapoda because M. is in the skeleton
    (malacostraca, worms_sans_malacostraca) = split_worms('Malacostraca',worms)
    ott.absorb(malacostraca)
    (cnidaria,low_priority_worms) = split_worms('Cnidaria',worms_sans_malacostraca)
    ott.absorb(cnidaria)

    # NCBI
    ncbi = taxonomies.load_ncbi()

    # Get mapping from NCBI to OTT, derived via SILVA and Genbank.
    # ... need to pass silva alignment, not OTT here
    mappings = load_ncbi_to_silva(ncbi, silva, silva_to_ott)

    ncbi_to_ott = align_ncbi(ncbi, silva, ott)
    ott.absorb(ncbi, ncbi_to_ott)

    debug_divisions('Reticularia splendens', ncbi, ott)

    # ... need to pass silva alignment, not OTT here
    compare_ncbi_to_silva(mappings, silva_to_ott)

    check_invariants(ott)

    for (ncbi_id, ott_id, name) in ncbi_ott_assignments.ncbi_assignments_list:
        n = ncbi.maybeTaxon(ncbi_id)
        if n != None:
            im = ncbi_to_ott.image(n)
            if im != None:
                im.setId(ott_id)
            else:
                print '** NCBI %s not mapped - %s' % (ncbi_id, name)
        else:
            print '** No NCBI taxon %s - %s' % (ncbi_id, name)

    # WoRMS
    low_priority_worms.taxon('Biota').synonym('life')
    # This is suboptimal, but the names are confusing the division logic
    low_priority_worms.taxon('Glaucophyta'). \
        absorb(low_priority_worms.taxon('Glaucophyceae'))
    a = align_worms(low_priority_worms, ott)
    ott.absorb(low_priority_worms, a)

    # The rest of Index Fungorum (maybe not a good idea)
    ott.absorb(fungorum_sans_fungi, align_fungorum_sans_fungi(fungorum_sans_fungi, ott))

    # GBIF
    gbif = taxonomies.load_gbif()
    gbif_to_ott = align_gbif(gbif, ott)
    ott.absorb(gbif, gbif_to_ott)
    debug_divisions('Enterobryus cingaloboli', gbif, ott)

    # Cylindrocarpon is now Neonectria
    cyl = gbif_to_ott.image(gbif.taxon('Cylindrocarpon', 'Ascomycota'))
    if cyl != None:
        cyl.setId('51754')

    # IRMNG
    irmng = taxonomies.load_irmng()

    hide_irmng(irmng)

    a = align_irmng(irmng, ott)
    if True:                   # Include taxa from irmng?
        ott.absorb(irmng, a)
    else:
        ott.align(a)
        a.transferProperties(irmng)

    taxonomies.link_to_h2007(ott)

    get_default_extinct_info_from_gbif(gbif, gbif_to_ott)

    check_invariants(ott)
    # consider try: ... except: print '**** Exception in patch_ott'
    patch_ott(ott)

    # Experimental...
    if False:
        unextinct_ncbi(ncbi, ott)

    # Remove all trees but the largest (or make them life incertae sedis)
    ott.deforestate()

    # -----------------------------------------------------------------------------
    # OTT id assignment

    # Force some id assignments... will try to automate this in the future.
    # Most of these come from looking at the otu-deprecated.tsv file after a
    # series of smasher runs.

    for (inf, sup, id) in [
            ('Tipuloidea', 'Diptera', '722875'),
            ('Saccharomycetes', 'Saccharomycotina', '989999'),
            ('Phaeosphaeria', 'Ascomycota', '5486272'),
            ('Synedra acus','Eukaryota','992764'),
            ('Epiphloea','Archaeplastida','5342325'),
            ('Epiphloea', 'Lichinales', '5342482'),
            ('Hessea','Archaeplastida','600099'),
            ('Morganella','Arthropoda','6400'),
            ('Rhynchonelloidea','Rhynchonellidae','5316010'),
            ('Morganella', 'Fungi', '973932'),
            ('Parmeliaceae', 'Lecanorales', '305904'),
            ('Cordana', 'Ascomycota', '946160'),
            ('Pseudofusarium', 'Ascomycota', '655794'),
            ('Marssonina', 'Dermateaceae', '372158'), # ncbi:324777
            ('Marssonia', 'Lamiales', '5512668'), # gbif:7268388
            # ('Gloeosporium', 'Pezizomycotina', '75019'),  # synonym for Marssonina
            ('Escherichia coli', 'Enterobacteriaceae', '474506'), # ncbi:562
            # ('Dischloridium', 'Trichocomaceae', '895423'),
            ('Exaiptasia pallida', 'Cnidaria', '135923'),
            ('Choanoflagellida', 'Holozoa', '202765'),
            ('Billardiera', 'Lamiales', '798963'),
            ('Pohlia', 'Foraminifera', '5325989'),
            ('Trachelomonas grandis', 'Bacteria', '58035'), # study ot_91 Tr46259
            ('Hypomyzostoma', 'Myzostomida', '552744'),   # was incorrectly in Annelida
    ]:
        tax = ott.maybeTaxon(inf, sup)
        if tax != None:
            tax.setId(id)

    # ott.taxon('474506') ...

    ott.taxonThatContains('Rhynchonelloidea', 'Sphenarina').setId('795939') # NCBI

    # Trichosporon is a mess, because it occurs 3 times in NCBI.
    trich = ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum')
    if trich != None:
        trich.setId('364222')

    #ott.image(fungi.taxon('11060')).setId('4107132') #Cryptococcus - a total mess

    # --------------------
    # Assign OTT ids to taxa that don't have them, re-using old ids when possible
    ids = Taxonomy.getTaxonomy('tax/prev_ott/', 'ott')

    # Edit the id source taxonomy to optimize id coverage

    # Kludge to undo lossage in OTT 2.9
    for taxon in ids.taxa():
        if (len(taxon.sourceIds) >= 2 and
            taxon.sourceIds[0].prefix == "ncbi" and
            taxon.sourceIds[1].prefix == "silva"):
            taxon.sourceIds.remove(taxon.sourceIds[0])

    # OTT 2.9 has both Glaucophyta and Glaucophyceae...
    # this creates an ambiguity when aligning.
    # Need to review this; maybe they *should* be separate taxa.
    g1 = ids.maybeTaxon('Glaucophyta')
    g2 = ids.maybeTaxon('Glaucophyceae')
    if g1 != None and g2 != None and g1 != g2:
        g1.absorb(g2)

    # Assign old ids to nodes in the new version
    ott.carryOverIds(ids) # Align & copy ids

    # Apply the additions (which already have ids assigned)
    print '-- Processing additions --'
    Addition.processAdditions(additions_clone_path, ott)

    # Mint ids for new nodes
    ott.assignNewIds(new_taxa_path)

    ott.check()

    report_on_h2007(h2007, h2007_to_ott)

    return ott

def hide_irmng(irmng):
    # Sigh...
    # https://github.com/OpenTreeOfLife/feedback/issues/302
    for root in irmng.roots():
        root.hide()
    with open('irmng_only_otus.csv', 'r') as infile:
        reader = csv.reader(infile)
        reader.next()           # header row
        for row in reader:
            if irmng.lookupId(row[0]) is not None:
                irmng.lookupId(row[0]).unhide()

def debug_divisions(name, ncbi, ott):
    print '##'
    ncbi.taxon(name).show()
    ott.taxon(name).show()
    foo = ott.taxon(name)
    while foo != None:
        print foo, foo.getDivision()
        foo = foo.parent
    print '##'


# ----- Ctenophora polysemy -----

def deal_with_ctenophora(ott):
    # Ctenophora is seriously messing up the division logic.
    # ncbi 1003038	|	33856	|	Ctenophora	|	genus	|	= diatom        OTT 103964
    # ncbi 10197 	|	6072	|	Ctenophora	|	phylum	|	= comb jellies  OTT 641212
    # ncbi 516519	|	702682	|	Ctenophora	|	genus	|	= cranefly      OTT 1043126

    # The comb jellies are already in the taxonomy at this point (from skeleton).

    # Add the diatom to OTT so that SILVA has something to map its diatom to
    # that's not the comb jellies.

    # To do this without creating a sibling-could homonym, we have to create
    # a place to put it.  This will be rederived from SILVA soon enough.
    establish('Bacillariophyta', ott, division='Eukaryota', ott_id='5342311')

    # Diatom.  Contains e.g. Ctenophora pulchella.
    ctenophora_diatom = establish('Ctenophora', ott,
                                  ancestor='Bacillariophyta',
                                  ott_id='103964')

    # The comb jelly should already be in skeleton, but include the code for symmetry.
    # Contains e.g. Leucothea multicornis
    ctenophora_jelly = establish('Ctenophora', ott,
                                 parent='Metazoa',
                                 ott_id='641212')

    # The fly will be added by NCBI; provide a node to map it to.
    # Contains e.g. Ctenophora dorsalis
    ctenophora_fly = establish('Ctenophora', ott,
                               division='Diptera',
                               ott_id='1043126')

    establish('Podocystis', ott, division='Fungi', ott_id='809209')
    establish('Podocystis', ott, parent='Bacillariophyta', ott_id='357108')

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/198
    establish('Euxinia', ott, division='Metazoa', source='ncbi:100781', ott_id='476941') #flatworm
    establish('Euxinia', ott, division='Metazoa', source='ncbi:225958', ott_id='329188') #amphipod

    # Discovered via failed inclusion test
    establish('Campanella', ott, division='Eukaryota', source='ncbi:168241', ott_id='136738') #alveolata
    establish('Campanella', ott, division='Fungi', source='ncbi:71870', ott_id='5342392')    #basidiomycete

    # Discovered via failed inclusion test
    establish('Diphylleia', ott, division='Eukaryota',      source='ncbi:177250', ott_id='4738987') #apusozoan
    establish('Diphylleia', ott, division='Chloroplastida', source='ncbi:63346' , ott_id='570408') #eudicot


# ----- SILVA -----

def align_silva(silva, ott):
    a = ott.alignment(silva)
    a.same(silva.taxonThatContains('Ctenophora', 'Ctenophora pulchella'),
           ott.taxon('103964'))
    #a.same(silva.taxonThatContains('Ctenophora', 'Beroe ovata'),
    #       ott.taxon('641212'))
    return a

# ----- Index Fungorum -----
# IF is pretty comprehensive for Fungi, but has an assortment of other
# things, mostly eukaryotic microbes.  We should treat the former as
# more authoritative than NCBI, and the latter as less authoritative
# than NCBI.

def split_fungorum(ott):
    fungorum = taxonomies.load_fung()

    fungi_root = fungorum.taxon('Fungi')
    fungi = fungorum.select(fungi_root)
    fungi_root.trim()

    print "Fungi in Index Fungorum has %s nodes"%fungi.count()
    return (fungi, fungorum)

def align_fungi(fungi, ott):
    a = ott.alignment(fungi)

    # *** Alignment to SILVA

    # 2014-03-07 Prevent a false match
    # https://groups.google.com/d/msg/opentreeoflife/5SAPDerun70/fRjA2M6z8tIJ
    # This is a fungus in Pezizomycotina
    # ### CHECK: was silva.taxon('Phaeosphaeria')
    # ott.notSame(ott.taxon('Phaeosphaeria', 'Rhizaria'), fungi.taxon('Phaeosphaeria', 'Ascomycota'))

    # 2014-04-08 This was causing Agaricaceae to be paraphyletic
    # ### CHECK: was silva.taxon('Morganella')
    # ott.notSame(ott.taxon('Morganella'), fungi.taxon('Morganella'))

    # 2014-04-08 More IF/SILVA bad matches
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/63
    # The notSame directives are unnecessary if SAR is a division
    for (name, f, o) in [('Acantharia', 'Fungi', 'Rhizaria'),   # fungus if:8 is nom. illegit. but it's also in gbif
                         ('Lacrymaria', 'Fungi', 'Alveolata'),
                         ('Steinia', 'Fungi', 'Alveolata'),   # also insect < Holozoa in irmng
                         #'Epiphloea',      # in Pezizomycotina < Opisth. / Rhodophyta  should be OK, Rh. is a division
                         #'Campanella',     # in Agaricomycotina < Nuclet. / SAR / Cnidaria
                         #'Bogoriella',     # in Verrucariaceae < Pezizomycotina < Euk. / Bogoriellaceae < Bacteria  should be ok
    ]:
        tax1 = fungi.maybeTaxon(name, f)
        if tax1 == None:
            print '** no %s in IF' % name # 'no Acantharia in IF'
        else:
            a.same(tax1, establish(name, ott, ancestor=f))

    # 2014-04-25 JAR
    # There are three Bostrychias: a rhodophyte, a fungus, and a bird.
    # The fungus name is a synonym for Cytospora.
    # ### CHECK: was silva.taxon
    if fungi.maybeTaxon('Bostrychia', 'Ascomycota') != None:
        if do_notSames:
            a.notSame(fungi.taxon('Bostrychia', 'Ascomycota'),
                      ott.taxon('Bostrychia', 'Rhodophyceae'))

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
    # ### CHECK: was silva.taxon
    # As of 2016-06-05, the fungus has changed its name to Melampsora, so there is no longer a problem.
    # a.notSame(fungi.taxon('Podocystis', 'Fungi'), ott.taxon('Podocystis', 'Stramenopiles'))

    a.same(fungi.taxon('Podocystis', 'Fungi'), ott.taxon('Podocystis', 'Fungi'))

    # Create a homonym (the one in Fungi, not the same as the one in Alveolata)
    # so that the IF Ciliophora can map to it
    establish('Ciliophora', ott, ancestor='Fungi', rank='genus', source='if:7660', ott_id='5343665')
    a.same(fungi.taxon('Ciliophora', 'Fungi'), ott.taxon('Ciliophora', 'Fungi'))

    # Create a homonym (the one in Fungi, not the same as the one in Rhizaria)
    # so that the IF Phaeosphaeria can map to it
    establish('Phaeosphaeria', ott, ancestor='Fungi', rank='genus', source='if:3951', ott_id='5486272')
    a.same(fungi.taxon('Phaeosphaeria', 'Fungi'), ott.taxon('Phaeosphaeria', 'Fungi'))

    # https://github.com/OpenTreeOfLife/feedback/issues/45
    # Unfortunately Choanoflagellida is currently showing up as
    # inconsistent.
    if False:
        a.same(fungorum.maybeTaxon('Choanoflagellida'),
               ott.maybeTaxon('Choanoflagellida', 'Opisthokonta'))

    return a

def align_fungorum_sans_fungi(sans, ott):
    a = ott.alignment(sans)
    a.same(sans.taxon('Byssus'), ott.taxon('Trentepohlia', 'Chlorophyta'))
    a.same(sans.taxon('Achlya'), ott.taxon('Achlya', 'Stramenopiles'))
    return a

# ----- Lamiales taxonomy from study 713 -----
# http://dx.doi.org/10.1186/1471-2148-10-352

def align_lamiales(study713, ott):
    a = ott.alignment(study713)
    # Without the explicit alignment of Chloroplastida, alignment thinks that
    # the study713 Chloroplastida cannot be the same as the OTT Chloroplastida,
    # because of something something something Buchnera (which is a
    # bacteria/plant polysemy).
    a.same(study713.taxon('Chloroplastida'), ott.taxon('Chloroplastida'))
    if do_notSames:
        a.notSame(study713.taxon('Buchnera', 'Orobanchaceae'), ott.taxon('Buchnera', 'Enterobacteriaceae'))
    return a

# ----- WoRMS -----
# splits worms into two parts: 1. the subtree rooted at taxon_name
# and 2. everything else
def split_worms(taxon_name,worms):
    # get the taxon with name=taxon_name from worms
    t = worms.taxon(taxon_name)
    # get the subtree rooted at this taxon
    subtree = worms.select(t)
    # remove all of the descendants of this taxon
    t.trim()
    worms_sans_subtree = worms
    return (subtree, worms_sans_subtree)

# ----- NCBI Taxonomy -----

def align_ncbi(ncbi, silva, ott):

    a = ott.alignment(ncbi)

    a.same(ncbi.taxon('Viridiplantae'), ott.taxon('Chloroplastida'))
    arch = establish('Archaeplastida', ncbi, division='Eukaryota') # No id
    ncbi.taxon('Eukaryota').take(arch)
    arch.take(ncbi.taxon('Viridiplantae'))
    arch.take(ncbi.taxon('Rhodophyta'))
    arch.take(ncbi.taxon('Glaucocystophyceae'))
    arch.unsourced = True

    a.same(ncbi.taxonThatContains('Ctenophora', 'Ctenophora pulchella'),
           ott.taxonThatContains('Ctenophora', 'Ctenophora pulchella')) # should be 103964
    a.same(ncbi.taxonThatContains('Ctenophora', 'Pleurobrachia bachei'),
           ott.taxon('641212')) # comb jelly
    a.same(ncbi.taxon('Ctenophora', 'Arthropoda'),
           ott.taxon('Ctenophora', 'Arthropoda')) # crane fly

    # David Hibbett has requested that for Fungi, only Index Fungorum
    # should be seen.  Rather than delete the NCBI fungal taxa, we just
    # mark them 'hidden' so they can be suppressed downstream.  This
    # preserves the identifier assignments, which may have been used
    # somewhere.
    ncbi.taxon('Fungi').hideDescendantsToRank('species')

    # - Alignment to OTT -

    #a.same(ncbi.taxon('Cyanobacteria'), silva.taxon('D88288/#3'))
    # #### Check - was fungi.taxon
    # ** No unique taxon found with this name: Burkea
    # ** No unique taxon found with this name: Coscinium
    # ** No unique taxon found with this name: Perezia
    # a.notSame(ncbi.taxon('Burkea', 'Viridiplantae'), ott.taxon('Burkea'))
    # a.notSame(ncbi.taxon('Coscinium', 'Viridiplantae'), ott.taxon('Coscinium'))
    # a.notSame(ncbi.taxon('Perezia', 'Viridiplantae'), ott.taxon('Perezia'))

    # JAR 2014-04-11 Discovered during regression testing
    # now handled in other ways
    # a.notSame(ncbi.taxon('Epiphloea', 'Rhodophyta'), ott.taxon('Epiphloea', 'Ascomycota'))

    # JAR attempt to resolve ambiguous alignment of Trichosporon in IF to
    # NCBI based on common member.
    # T's type = T. beigelii, which is current, according to Mycobank,
    # but it's not in our copy of IF.
    # I'm going to use a different exemplar, Trichosporon cutaneum, which
    # seems to occur in all of the source taxonomies.
    a.same(ncbi.taxon('5552'),
           ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))

    # 2014-04-23 In new version of IF - obvious misalignment
    # #### Check - was fungi.taxon
    # a.notSame(ncbi.taxon('Crepidula', 'Gastropoda'), ott.taxon('Crepidula', 'Microsporidia'))
    # a.notSame(ncbi.taxon('Hessea', 'Viridiplantae'), ott.taxon('Hessea', 'Microsporidia'))
    # 2014-04-23 Resolve ambiguity introduced into new version of IF
    # http://www.speciesfungorum.org/Names/SynSpecies.asp?RecordID=331593
    # #### Check - was fungi.taxon
    a.same(ncbi.taxon('Gymnopilus spectabilis var. junonius'), ott.taxon('Gymnopilus junonius'))

    # JAR 2014-04-23 More sample contamination in SILVA 115
    # #### Check - was fungi.taxon
    # a.same(ncbi.taxon('Lamprospora'), ott.taxon('Lamprospora', 'Pyronemataceae'))

    # JAR 2014-04-25
    # ### CHECK: was silva.taxon
    # a.notSame(ncbi.taxon('Bostrychia', 'Aves'), ott.taxon('Bostrychia', 'Rhodophyceae'))

    # Dail 2014-03-31 https://github.com/OpenTreeOfLife/feedback/issues/5
    # updated 2015-06-28 NCBI Katablepharidophyta = SILVA Kathablepharidae.
    # ### CHECK: was silva.taxon
    a.same(ncbi.taxon('Katablepharidophyta'), ott.taxon('Kathablepharidae'))
    # was: ott.taxon('Katablepharidophyta').hide()

    # probably not needed
    a.same(ncbi.taxon('Ciliophora', 'Alveolata'), ott.taxon('Ciliophora', 'Alveolata'))

    # SILVA has Diphylleia < Palpitomonas < Incertae Sedis < Eukaryota
    # IRMNG has Diphylleida < Diphyllatea < Apusozoa < Protista
    # They're probably the same thing.  So not sure why this is being
    # handled specially.
    if do_notSames:
        a.notSame(ncbi.taxon('Diphylleia', 'Chloroplastida'),
                  ott.taxonThatContains('Diphylleia', 'Diphylleia rotans'))

    a.same(ncbi.taxon('Podocystis', 'Bacillariophyta'),
           ott.taxon('Podocystis', 'Bacillariophyta'))

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/198 see above
    a.same(ncbi.taxon('Euxinia', 'Pseudostomidae'), ott.taxon('476941'))
    a.same(ncbi.taxon('Euxinia', 'Crustacea'), ott.taxon('329188'))

    # NCBI has Leotiales as a synonym for Helotiales, but h2007 and IF
    # have them as separate orders.  This shouldn't cause a problem, but does.
    ncbi.taxon('Helotiales').notCalled('Leotiales')

    return a

# Maps taxon in NCBI taxonomy to SILVA-derived OTT taxon

def load_ncbi_to_silva(ncbi, silva, silva_to_ott):
    mappings = {}
    flush = []
    with open('feed/silva/out/ncbi_to_silva.tsv', 'r') as infile:
        reader = csv.reader(infile, delimiter='\t')
        for (ncbi_id, silva_cluster_id) in reader:
            n = ncbi.maybeTaxon(ncbi_id)
            if n != None:
                s = silva.maybeTaxon(silva_cluster_id)
                if s != None:
                    so = silva_to_ott.image(s)
                    if so != None:
                        if n in mappings:
                            # 213 of these
                            # print '** NCBI id maps to multiple SILVA clusters', n
                            mappings[n] = True
                            flush.append(n)
                        else:
                            mappings[n] = so
                    else:
                        print '** no OTT taxon for cluster', silva_cluster_id
                else:
                    # Too many of these now, and not sure what to do about them.
                    # print '| no cluster %s for %s' % (silva_cluster_id, n)
                    True
    for n in flush:
        if n in mappings:
            del mappings[n]
    return mappings

# Report on differences between how NCBI and OTT map to SILVA

def compare_ncbi_to_silva(mappings, silva_to_ott):
    problems = 0
    for taxon in mappings:
        t1 = mappings[taxon]
        t2 = silva_to_ott.image(taxon)
        if t1 != t2:
            problems += 1
            if t2 != None and t1.name == t2.name:
                div = t1.divergence(t2)
                if div != None:
                    print '| %s -> (%s, %s) coalescing at (%s, %s)' % \
                        (taxon, t1, t2, div[0], div[1])
    print '* %s NCBI taxa map differently by cluster vs. by name' % problems

def align_ncbi_to_silva(mappings, a):
    changes = 0
    for taxon in mappings:
        a.same(taxon, mappings[taxon])
        changes += 1
    print changes, '| NCBI taxa mapped to SILVA clusters'


def align_worms(worms, ott):
    a = ott.alignment(worms)
    a.same(worms.taxon('Plantae'), ott.taxon('Archaeplastida'))

    a.same(worms.taxonThatContains('Trichosporon', 'Trichosporon lodderae'),
           ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))
    a.same(worms.taxonThatContains('Trichoderma', 'Trichoderma koningii'),
           ott.taxonThatContains('Trichoderma', 'Trichoderma koningii'))
    # 2016-07-28 Noticed this in deprecated.tsv:
    # NCBI puts Myzostomida outside of Annelida.  To ensure matches, we have
    # to do so here as well, because Annelida is a barrier node and somewhat
    # difficult to cross.
    worms.taxon('Animalia').take(worms.taxon('Myzostomida'))

    # extinct foram, polyseym risk with extant bryophyte
    # worms.taxon('Pohlia', 'Rhizaria').prune(this_source)

    # Annelida is a barrier, need to put Sipuncula inside it
    worms.taxon('Annelida').take(worms.taxon('Sipuncula'))

    return a

# ----- GBIF (Global Biodiversity Information Facility) taxonomy -----

def align_gbif(gbif, ott):

    a = ott.alignment(gbif)

    plants = fix_plants(gbif)
    a.same(plants, ott.taxon('Archaeplastida'))

    # GBIF puts this one directly in Animalia, but Annelida is a barrier node
    gbif.taxon('Annelida').take(gbif.taxon('Echiura'))
    # similarly
    gbif.taxon('Cnidaria').take(gbif.taxon('Myxozoa'))

    gbif.taxon('Viruses').hide()

    # Fungi suppressed at David Hibbett's request
    gbif.taxon('Fungi').hideDescendantsToRank('species')

    # Suppressed at Laura Katz's request
    gbif.taxonThatContains('Bacteria','Bacillus').hideDescendants()
    gbif.taxonThatContains('Archaea','Halobacteria').hideDescendants()

    # - Alignment -

    #a.same(gbif.taxon('Cyanobacteria'), silva.taxon('Cyanobacteria','Cyanobacteria')) #'D88288/#3'

    # Automatic alignment makes the wrong choice for this one
    # a.same(ncbi.taxon('5878'), gbif.taxon('10'))    # Ciliophora
    a.same(gbif.taxon('10'), ott.taxon('Ciliophora', 'Alveolata'))  # in Protozoa
    # Not needed?
    # a.same(ott.taxon('Ciliophora', 'Ascomycota'), gbif.taxon('3269382')) # in Fungi

    # Automatic alignment makes the wrong choice for this one
    # NCBI says ncbi:29178 is in Rhizaria in Eukaryota and contains Allogromida (which is not in GBIF)
    # OTT 2.8 has 936399 = in Retaria (which isn't in NCBI) extinct_inherited ? - no good.
    # GBIF 389 is in Protozoa... but it contains nothing!!  No way to identify it other than by id.
    #   amoeboid ...
    a.same(gbif.taxon('389'), ott.taxon('Foraminifera', 'Rhizaria'))  # Foraminifera gbif:4983431

    # Tetrasphaera is a messy multi-way homonym
    #### Check: was ncbi.taxon
    a.same(gbif.taxon('Tetrasphaera','Intrasporangiaceae'), ott.taxon('Tetrasphaera','Intrasporangiaceae'))

    # Bad alignments to NCBI
    # #### THESE NEED TO BE CHECKED - was ncbi.taxon

    # Labyrinthomorpha (synonym for Labyrinthulomycetes)
    # No longer in GBIF... the one in IRMNG is a Cambrian sponge-like thing
    # a.notSame(ott.taxon('Labyrinthomorpha', 'Stramenopiles'), gbif.taxon('Labyrinthomorpha'))

    # a.notSame(ott.taxon('Ophiurina', 'Echinodermata'), gbif.taxon('Ophiurina','Ophiurinidae'))
    #  taken care of in taxonomies.py

    # There is a test for this.  The GBIF taxon no longer exists.
    # a.notSame(ott.taxon('Rhynchonelloidea', 'Brachiopoda'), gbif.taxon('Rhynchonelloidea'))

    # There are tests.  Seems OK
    if do_notSames:
        a.notSame(gbif.taxon('Neoptera', 'Diptera'), ott.taxonThatContains('Neoptera', 'Lepidoptera'))

    # a.notSame(gbif.taxon('Tipuloidea', 'Chiliocyclidae'), ott.taxon('Tipuloidea', 'Diptera')) # genus Tipuloidea
    #  taken care of in taxonomies.py
    # ### CHECK: was silva.taxon
    # SILVA = GN013951 = Tetrasphaera (bacteria)

    # This one seems to have gone away given changes to GBIF
    # a.notSame(gbif.taxon('Gorkadinium', 'Dinophyta'),
    #              ott.taxon('Tetrasphaera', 'Intrasporangiaceae')) # = Tetrasphaera in Protozoa

    # Rick Ree 2014-03-28 https://github.com/OpenTreeOfLife/reference-taxonomy/issues/37
    # ### CHECK: was ncbi.taxon
    # a.same(gbif.taxon('Calothrix', 'Rivulariaceae'), ott.taxon('Calothrix', 'Rivulariaceae'))
    a.same(gbif.taxon('Chlorella', 'Chlorellaceae'), ott.taxon('Chlorella', 'Chlorellaceae'))
    a.same(gbif.taxon('Myrmecia', 'Microthamniales'), ott.taxon('Myrmecia', 'Microthamniales'))

    # JAR 2014-04-18 attempt to resolve ambiguous alignment of
    # Trichosporon in IF and GBIF based on common member
    a.same(gbif.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'),
           ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))

    # Obviously the same genus, can't tell what's going on
    # if:17806 = Hygrocybe = ott:282216
    # #### CHECK: was fungi
    a.same(gbif.taxon('Hygrocybe'), ott.taxon('Hygrocybe', 'Hygrophoraceae'))

    # JAR 2014-04-23 More sample contamination in SILVA 115
    # redundant
    # a.same(gbif.taxon('Lamprospora'), fungi.taxon('Lamprospora'))

    # JAR 2014-04-23 IF update fallout
    # ### CHECK: was ncbi.taxon
    a.same(gbif.taxonThatContains('Penicillium', 'Penicillium expansum'),
           ott.taxonThatContains('Penicillium', 'Penicillium expansum'))

    # https://github.com/OpenTreeOfLife/feedback/issues/45
    if False:
        a.same(gbif.taxon('Choanoflagellida'),
               ott.taxon('Choanoflagellida', 'Opisthokonta'))

    # diatom
    a.same(gbif.taxonThatContains('Ctenophora', 'Ctenophora pulchella'),
           ott.taxonThatContains('Ctenophora', 'Ctenophora pulchella'))

    # comb jellies
    a.same(gbif.taxonThatContains('Ctenophora', 'Pleurobrachia bachei'),
           ott.taxonThatContains('Ctenophora', 'Pleurobrachia bachei'))

    a.same(gbif.taxonThatContains('Trichoderma', 'Trichoderma koningii'),
           ott.taxonThatContains('Trichoderma', 'Trichoderma koningii'))

    # Polysemy with an order in Chaetognatha (genus is a brachiopod)
    # https://github.com/OpenTreeOfLife/feedback/issues/306
    establish('Phragmophora', ott, ancestor='Rhynchonellata', rank='genus', source='gbif:5430295')
    a.same(gbif.taxon('5430295'), ott.taxon('Phragmophora', 'Rhynchonellata'))

    # 2016 GBIF seems to have Fragillariophyceae in a class Bacillariophyceae.
    # In NCBI (and everywhere else) the taxon called 'Bacillariophyceae'
    # is a sibling of Fragillariophyceae in Bacillariophyta.
    bac = gbif.maybeTaxon('Bacillariophyceae')
    if bac != None:
        a.same(bac, ott.taxon('Bacillariophyta', 'SAR'))

    # Annelida is a barrier, need to put Sipuncula inside it
    gbif.taxon('Annelida').take(gbif.taxon('Sipuncula'))

    # IRMNG has better placement for these things
    target = gbif.taxon('Plantae').parent
    for name in ['Pithonella',
                 'Vavosphaeridium',
                 'Sphaenomonas',
                 'Orthopithonella',
                 'Euodiella',
                 'Medlinia',
                 'Quadrodiscus',
                 'Obliquipithonella',
                 'Damassadinium',
                 'Conion',
                 'Gaillionella']:
        taxon = gbif.maybeTaxon(name, 'Plantae')
        if taxon != None:
            target.take(taxon)
            taxon.incertaeSedis()

    # Noticed while scanning species polysemies
    gbif.taxon('Euglenales').take(gbif.taxon('Heteronema', 'Rhodophyta'))

    # WoRMS says it's not a fungus
    gbif.taxonThatContains('Minchinia', 'Minchinia cadomensis').prune(this_source)

    return a

def fix_plants(taxonomy):

    plants = taxonomy.taxon('Plantae')

    chlor = establish('Chloroplastida', taxonomy, parent='Plantae') # No id
    chlor.unsourced = True
    plants.take(chlor)

    # Dispose of all the children of Plantae
    bac = taxonomy.maybeTaxon('Bacillariophyta', 'Plantae')
    if bac != None:
        plants.parent.take(bac)
    to_move = []
    for plant in plants.children:
        if (plant.name != 'Rhodophyta' and plant.name != 'Glaucophyta'
            and plant.rank.level <= Rank.FAMILY_RANK.level):
            to_move.append(plant)
    for plant in to_move:
        un = not plant.isPlaced()
        chlor.take(plant)
        if un: plant.unplaced()

    # straighten out Byssus division
    ulv = taxonomy.maybeTaxon('Ulvophyceae')
    if ulv.parent == chlor.parent:
        chlor.take(ulv)

    return plants

# ----- Interim Register of Marine and Nonmarine Genera (IRMNG) -----

def align_irmng(irmng, ott):

    a = ott.alignment(irmng)

    plants = fix_plants(irmng)
    a.same(plants, ott.taxon('Archaeplastida'))

    # irmng.taxon('Viruses').hide()  see taxonomies.py

    # Fungi suppressed at David Hibbett's request
    irmng.taxon('Fungi').hideDescendantsToRank('species')

    # Microbes suppressed at Laura Katz's request
    irmng.taxonThatContains('Bacteria','Escherichia coli').hideDescendants()
    irmng.taxonThatContains('Archaea','Halobacteria').hideDescendants()

    # Cnidaria is a barrier node
    irmng.taxon('Cnidaria').take(irmng.taxon('Myxozoa'))
    # Annelida is a barrier, need to put Sipuncula inside it
    irmng.taxon('Annelida').take(irmng.taxon('Sipuncula'))

    a.same(irmng.taxon('1381293'), ott.taxon('Veronica', 'Plantaginaceae'))  # ott:648853
    # genus Tipuloidea (not superfamily) ott:5708808 = gbif:6101461
    # Taken care of in assemble_ott.py:
    # a.same(ott.taxon('Tipuloidea', 'Dicondylia'), irmng.taxon('1170022'))
    # IRMNG has four Tetrasphaeras.
    a.same(irmng.taxon('Tetrasphaera','Intrasporangiaceae'), ott.taxon('Tetrasphaera','Intrasporangiaceae'))
    ottgork = ott.maybeTaxon('Gorkadinium','Dinophyceae')
    if ottgork != None:
        a.same(irmng.taxon('Gorkadinium','Dinophyceae'), ottgork)

    # JAR 2014-04-18 attempt to resolve ambiguous alignment of
    # Match Trichosporon in IRMNG to one of three in OTT based on common member.
    # Trichosporon in IF = if:10296 genus in Trichosporonaceae, contains cutaneum
    a.same(irmng.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'), \
           ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))


    # https://github.com/OpenTreeOfLife/feedback/issues/45
    # IRMNG has Choanoflagellida < Zoomastigophora < Sarcomastigophora < Protozoa
    # might be better to look for something it contains
    a.same(irmng.taxon('Choanoflagellida', 'Zoomastigophora'),
             ott.taxon('Choanoflagellida', 'Eukaryota'))

    # probably not needed
    a.same(irmng.taxon('239'), ott.taxon('Ciliophora', 'Alveolata'))  # in Protista
    # Gone away...
    # a.same(ott.taxon('Ciliophora', 'Ascomycota'), irmng.taxon('Ciliophora', 'Ascomycota'))

    # Could force this to not match the arthropod.  But much easier just to delete it.
    irmng.taxon('Morganella', 'Brachiopoda').prune(this_source)
    #  ... .notSame(ott.taxon('Morganella', 'Arthropoda'))

    def trouble(name, ancestor, not_ancestor):
        probe = irmng.maybeTaxon(name, ancestor)
        if probe == None: return
        if do_notSames:
            a.notSame(probe, ott.taxon(name, not_ancestor))
        else:
            probe.prune(this_source)

    # JAR 2014-04-24 false match
    # IRMNG has one in Pteraspidomorphi (basal Chordate) as well as a
    # protozoan (SAR; ncbi:188977).
    trouble('Protaspis', 'Chordata', 'Cercozoa')

    # JAR 2014-04-18 while investigating hidden status of Coscinodiscus radiatus.
    # tests
    trouble('Coscinodiscus', 'Porifera', 'Stramenopiles')

    # 2015-09-10 Inclusion test failing irmng:1340611
    trouble('Retaria', 'Brachiopoda', 'Rhizaria')

    # 2015-09-10 Inclusion test failing irmng:1289625
    trouble('Campanella', 'Cnidaria', 'SAR')

    # Bad homonyms
    trouble('Neoptera', 'Tachinidae', 'Pterygota')
    trouble('Hessea', 'Holozoa', 'Fungi')

    a.same(irmng.taxonThatContains('Trichoderma', 'Trichoderma koningii'),
           ott.taxonThatContains('Trichoderma', 'Trichoderma koningii'))

    # https://github.com/OpenTreeOfLife/feedback/issues/241
    # In IRMNG L. and S. are siblings (children of Actinopterygii), but in NCBI
    # Lepisosteiformes is a synonym of Semionotiformes (in Holostei, etc.).
    irmng.taxon('Semionotiformes').absorb(irmng.taxon('Lepisosteiformes'))
    irmng.taxon('Semionotiformes').extant()

    # From deprecated.tsv file for OTT 2.10
    irmng.taxon('Plectospira', 'Brachiopoda').prune(this_source)    # extinct, polysemy with SAR
    irmng.taxon('Leptomitus', 'Porifera').prune(this_source)  # extinct, SAR polysemy, =gbif:3251526

    # Annelida is a barrier, need to put Sipuncula inside it
    irmng.taxon('Annelida').take(irmng.taxon('Sipuncula'))

    # Noticed while scanning species polysemies
    irmng.taxon('Peranemaceae').take(irmng.maybeTaxon('Heteronema', 'Rhodophyta'))

    # 2016-10-28 Noticed Goeppertia wrongly extinct while eyeballing 
    # the deprecated.tsv file
    irmng.taxon('Goeppertia', 'Pteridophyta').prune(this_source)

    return a

# ----- Final patches -----

def patch_ott(ott):

    # Romina 2014-04-09: Hypocrea = Trichoderma.
    # IF and all the other taxonomies have both Hypocrea and Trichoderma.
    # Need to merge them.
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/86
    # Hypocrea rufa is the type species for genus Hypocrea, and it's the same as
    # Trichoderma viride.
    ott.taxon('Hypocrea').absorb(ott.taxonThatContains('Trichoderma', 'Trichoderma viride'))
    ott.taxon('Hypocrea rufa').absorb(ott.taxon('Trichoderma viride'))

    # Romina https://github.com/OpenTreeOfLife/reference-taxonomy/issues/42
    # this seems to have fixed itself
    # ott.taxon('Hypocrea lutea').absorb(ott.taxon('Trichoderma deliquescens'))

    # 2014-01-27 Joseph: Quiscalus is incorrectly in
    # Fringillidae instead of Icteridae.  NCBI is wrong, GBIF is correct.
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/87
    ott.taxon('Icteridae').take(ott.taxon('Quiscalus', 'Fringillidae'))

    # Misspelling in GBIF... seems to already be known
    # Stephen email to JAR 2014-01-26
    # ott.taxon("Torricelliaceae").synonym("Toricelliaceae")


    # Joseph 2014-01-27 https://code.google.com/p/gbif-ecat/issues/detail?id=104
    ott.taxon('Parulidae').take(ott.taxon('Myiothlypis', 'Passeriformes'))
    # I don't get why this one isn't a major_rank_conflict !? - bug. (so to speak.)
    ott.taxon('Blattodea').take(ott.taxon('Phyllodromiidae'))

    # See above (occurs in both IF and GBIF).  Also see issue #67
    ott.taxonThatContains('Chlamydotomus', 'Chlamydotomus beigelii').incertaeSedis()

    # Joseph Brown 2014-01-27
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/87
    # Occurs as Sakesphorus bernardi in ncbi, gbif, irmng, as Thamnophilus bernardi in bgif
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
    ott.taxon('Adlerocystis', 'Fungi').incertaeSedis()

    # "No clear identity has emerged"
    #  http://forestis.rsvs.ulaval.ca/REFERENCES_X/phylogeny.arizona.edu/tree/eukaryotes/accessory/parasitic.html
    # Need to hide it because it clutters base of Fungi
    if ott.maybeTaxon('Amylophagus','Fungi') != None:
        ott.taxon('Amylophagus','Fungi').incertaeSedis()

    # Bad synonym - Tony Rees 2014-01-28
    # https://groups.google.com/d/msg/opentreeoflife/SrI7KpPgoPQ/ihooRUSayXkJ
    if ott.maybeTaxon('Lemania pluvialis') != None:
        ott.taxon('Lemania pluvialis').prune("make-ott.py")

    # Tony Rees 2014-01-29
    # https://groups.google.com/d/msg/opentreeoflife/SrI7KpPgoPQ/wTeD17GzOGoJ
    trigo = ott.maybeTaxon('Trigonocarpales')
    if trigo != None: trigo.extinct()

    #Pinophyta and daughters need to be deleted; - Bryan 2014-01-28
    #Lycopsida and daughters need to be deleted;
    #Pteridophyta and daughters need to be deleted;
    #Gymnospermophyta and daughters need to be deleted;
    for name in ['Pinophyta', 'Pteridophyta', 'Gymnospermophyta']:
        if ott.maybeTaxon(name,'Chloroplastida'):
            ott.taxon(name,'Chloroplastida').incertaeSedis()

    # Patches from the Katz lab to give decent parents to taxa classified
    # as Chromista or Protozoa
    print '-- Chromista/Protozoa spreadsheet from Katz lab --'
    fixChromista(ott)
    # 2016-06-30 deleted from spreadsheet because ambiguous:
    #   Enigma,Protozoa,Polychaeta ,,,,, -
    #   Acantharia,Protozoa,Radiozoa,,,,,
    #   Lituolina,Chromista,Lituolida ,WORMS,,,,


    print '-- more patches --'

    # From Laura and Dail on 5 Feb 2014
    # https://groups.google.com/d/msg/opentreeoflife/a69fdC-N6pY/y9QLqdqACawJ
    tax = ott.maybeTaxon('Chlamydiae/Verrucomicrobia group')
    if tax != None and tax.name != 'Bacteria':
        tax.rename('Verrucomicrobia group')
    # The following is obviated by algorithm changes
    # ott.taxon('Heterolobosea','Discicristata').absorb(ott.taxon('Heterolobosea','Percolozoa'))
    tax = ott.taxonThatContains('Excavata', 'Euglena')
    if tax != None:
        tax.take(ott.taxon('Oxymonadida','Eukaryota'))

    # There is no Reptilia in OTT 2.9, so this can probably be deleted
    if ott.maybeTaxon('Reptilia') != None:
        ott.taxon('Reptilia').hide()

    # Chris Owen patches 2014-01-30
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/88
    ott.taxon('Protostomia').take(ott.taxonThatContains('Chaetognatha','Sagittoidea'))
    ott.taxon('Lophotrochozoa').take(ott.taxon('Platyhelminthes'))
    ott.taxon('Lophotrochozoa').take(ott.taxon('Gnathostomulida'))
    ott.taxon('Bilateria').take(ott.taxon('Acoela'))
    ott.taxon('Bilateria').take(ott.taxon('Xenoturbella'))
    ott.taxon('Bilateria').take(ott.taxon('Nemertodermatida'))
    # Myzostomida no longer in Annelida
    # ott.taxon('Polychaeta','Annelida').take(ott.taxon('Myzostomida'))
    # https://dx.doi.org/10.1007/s13127-011-0044-4
    # Not in deuterostomes
    ott.taxon('Bilateria').take(ott.taxon('Xenacoelomorpha'))
    if ott.maybeTaxon('Staurozoa') != None:
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

    ##### RECOVER THIS SOMEHOW --
    # ott.taxon('Scutellaria','Lamiaceae').absorb(ott.image(gbif.taxon('Salazaria')))
    # IRMNG 1288740 not in newer IRMNG

    if False:
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
    for child in ott.taxon('Homo', 'Primates').children:
        if child.name != 'Homo sapiens':
            child.extinct()
    for child in ott.taxon('Homo sapiens', 'Primates').children:
        if child.name != 'Homo sapiens sapiens':
            child.extinct()

    # JAR 2014-03-07 hack to prevent H.s. from being extinct due to all of
    # its subspecies being extinct.
    # I wish I knew what the authority for the H.s.s. name was.
    # (Linnaeus maybe?)
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
    for name in [
            'Temnospondyli', # http://tolweb.org/tree?group=Temnospondyli
            'Eobatrachus', # https://en.wikipedia.org/wiki/Eobatrachus
            'Vulcanobatrachus', # https://en.wikipedia.org/wiki/Vulcanobatrachus
            'Beelzebufo', # https://en.wikipedia.org/wiki/Beelzebufo
            'Iridotriton', # https://en.wikipedia.org/wiki/Iridotriton
            'Baurubatrachus', # https://en.wikipedia.org/wiki/Baurubatrachus
            'Acritarcha', # # JAR 2014-04-26

    ]:
        tax = ott.maybeTaxon(name)
        if tax != None: tax.extinct()

    # Dail 2014-03-31 https://github.com/OpenTreeOfLife/feedback/issues/4
    # "The parent [of Lentisphaerae] should be Bacteria and not Verrucomicrobia"
    # no evidence given
    bact = ott.taxonThatContains('Bacteria', 'Lentisphaerae')
    if bact != None:
        bact.take(ott.taxon('Lentisphaerae'))

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
    cyph = ott.maybeTaxon('Cyphellopsis','Cyphellaceae')
    if cyph != None:
        cyph.unhide()
        if ott.maybeTaxon('Cyphellopsis','Niaceae') != None:
            cyph.absorb(ott.taxon('Cyphellopsis','Niaceae'))

    ott.taxon('Diaporthaceae').take(ott.taxon('Phomopsis'))
    ott.taxon('Valsaceae').take(ott.taxon('Valsa', 'Fungi'))
    ott.taxon('Agaricaceae').take(ott.taxon('Cystoderma','Fungi'))
    # Invert the synonym relationship
    ott.taxon('Hypocrea lutea').absorb(ott.taxon('Trichoderma deliquescens'))

    # Fold Norops into Anolis
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/31
    # TBD: Change species names from Norops X to Anolis X for all X
    ott.taxon('Anolis').absorb(ott.maybeTaxon('Norops', 'Iguanidae'))

    for (name, super) in [
        # JAR 2014-04-08 - these are in study OTUs - see IRMNG
        ('Inseliellum', None),
        ('Conus', 'Gastropoda'),
        ('Patelloida', None),
        ('Phyllanthus', 'Phyllanthaceae'),
        ('Stelis','Orchidaceae'),
        ('Chloris', 'Poaceae'),
        ('Acropora', 'Acroporidae'),
        ('Diadasia', None),

        # JAR 2014-04-24
        # grep "ncbi:.*extinct_inherited" tax/ott/taxonomy.tsv | head
        ('Tarsius', None),
        ('Odontesthes', None),
        ('Leiognathus', 'Chordata'),
        ('Oscheius', None),
        ('Cicindela', None),
        ('Leucothoe', 'Ericales'),
        ('Hydrornis', None),
        ('Bostrychia harveyi', None), #fungus
        ('Agaricia', None), #coral
        ('Dischidia', None), #eudicot

        # JAR 2014-05-13
        ('Saurischia', None),
        # there are two of these, maybe should be merged.
        # 'Myoxidae', 'Rodentia'),

        # JAR 2014-05-13 These are marked extinct by IRMNG but are all in NCBI
        # and have necleotide sequences
        ('Zemetallina', None),
        ('Nullibrotheas', None),
        ('Fissiphallius', None),
        ('Nullibrotheas', None),
        ('Sinelater', None),
        ('Phanerothecium', None),
        ('Cephalotaxaceae', None),
        ('Vittaria elongata', None),
        ('Neogymnocrinus', None),
    ]:
        if super == None:
            tax = ott.maybeTaxon(name)
        else:
            tax = ott.maybeTaxon(name, super)
        if tax != None: tax.extant()

    # JAR 2014-05-08 while looking at the deprecated ids file.
    # http://www.theplantlist.org/tpl/record/kew-2674785
    ott.taxon('Berendtiella rugosa').synonym('Berendtia rugosa')

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

    # JAR 2015-07-21 noticed, obviously wrong
    ott.taxonThatContains('Ophiurina', 'Acrocnida brachiata').extant()

    # straightening out an awful mess
    ott.taxon('Saccharomycetes', 'Saccharomycotina').extant()  # foo.  don't know who sets this

    ott.taxonThatContains('Rhynchonelloidea', 'Sphenarina').extant() # NCBI

    # https://github.com/OpenTreeOfLife/feedback/issues/133
    ott.taxon('Pipoidea', 'Amphibia').take(ott.taxon('Cordicephalus', 'Amphibia'))

    # This is a randomly chosen bivalve to force Bivalvia to not be extinct
    ott.taxon('Corculum cardissa', 'Bivalvia').extant()
    # Similarly for roaches
    ott.taxon('Periplaneta americana', 'Blattodea').extant()

    # https://github.com/OpenTreeOfLife/feedback/issues/159
    ott.taxon('Nesophontidae').extinct()

    # "Old" patch system
    TsvEdits.edit(ott, 'feed/ott/edits/')

    # JAR 2016-06-30 Fixing a warning from 'report_on_h2007'
    # There really ought to be a family (Hyaloraphidiaceae, homonym) in
    # between, but it's not really necessary, so I won't bother
    ott.taxon('Hyaloraphidiales', 'Fungi').take(ott.taxon('Hyaloraphidium', 'Fungi'))

    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/195
    ott.taxon('Opisthokonta').setRank('no rank')

    # https://github.com/OpenTreeOfLife/feedback/issues/177
    ott.taxon('Amia fasciata').prune('https://github.com/OpenTreeOfLife/feedback/issues/177')

    # https://github.com/OpenTreeOfLife/feedback/issues/127
    # single species, name not accepted
    ott.taxon('Cestracion', 'Sphyrnidae').prune('https://github.com/OpenTreeOfLife/feedback/issues/127')

    # Related to https://github.com/OpenTreeOfLife/feedback/issues/307
    pter = ott.maybeTaxon('Pteridophyta')
    if pter != None and pter.parent == ott.taxon('Archaeplastida'):
        for child in pter.getChildren():
            child.unplaced()
        ott.taxon('Tracheophyta').absorb(pter)

    # https://github.com/OpenTreeOfLife/feedback/issues/221
    for name in ['Elephas cypriotes',         # NCBI
                 'Elephas antiquus',          # NCBI
                 'Elephas sp. NHMC 20.2.2.1', # NCBI
                 'Mammuthus',                 # NCBI
                 'Parelephas',                # GBIF
                 'Numidotheriidae',           # GBIF
                 'Barytheriidae',             # GBIF
                 'Anthracobunidae',           # GBIF
                 ]:
        taxon = ott.maybeTaxon(name, 'Proboscidea')
        if taxon != None:
            taxon.extinct()

    # From 2.10 deprecated list
    for (name, anc) in [
                 # Sphaerulina	if:5128,ncbi:237179,worms:100120,worms:100117,gbif:2621555,gbif:2574294,gbif:7254927,gbif:2564487,irmng:1291796	newly-hidden[extinct]	Sphaerulina	=
                 # Cucurbita	ncbi:3660,gbif:2874506,irmng:1009179	newly-hidden[extinct]	Cucurbita	=	synthesis
                 # Tuber	if:5629,ncbi:36048,gbif:7257845,gbif:7257854,gbif:2593130,gbif:5237010,irmng:1120184,irmng:1029932	newly-hidden[extinct]	Tuber	=
                 # Blastocystis	silva:U26177/#4,ncbi:12967,if:20081,gbif:3269640,irmng:1031549	newly-hidden[extinct]	Blastocystis	=
                 # Clavulinopsis	if:17324,ncbi:104211,gbif:2521976,irmng:1340486	newly-hidden[extinct]	Clavulinopsis	=
                 # Nesophontidae	gbif:9467,irmng:104821	newly-hidden[extinct]	Nesophontidae	=
                 # Polystoma	ncbi:92216,gbif:2503819,irmng:1269690,irmng:1269737	newly-hidden[extinct]	Polystoma	=
                 # Rustia	ncbi:86991,gbif:2904559,irmng:1356264	newly-hidden[extinct]	Rustia	=
                 ('Thalassiosira guillardii', 'SAR'),    # mistake in WoRMS
            ]:
        taxon = ott.maybeTaxon(name, anc)
        if taxon != None:
            taxon.extant()

    # we were getting extinctness from IRMNG, but now it's suppressed
    ott.taxon('Dinaphis', 'Aphidoidea').extinct()

    # Yan Wong https://github.com/OpenTreeOfLife/reference-taxonomy/issues/116
    # fung.taxon('Mycosphaeroides').extinct()  - gone
    if ott.maybeTaxon('Majasphaeridium'):
        ott.taxon('Majasphaeridium').extinct() # From IF

    # https://github.com/OpenTreeOfLife/feedback/issues/64
    ott.taxon('Plagiomene').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/65
    ott.taxon('Worlandia').extinct() # from GBIF

    # 2015-09-11 https://github.com/OpenTreeOfLife/feedback/issues/72
    ott.taxon('Myeladaphus').extinct() # from GBIF

    # 2015-09-11 https://github.com/OpenTreeOfLife/feedback/issues/78
    ott.taxon('Oxyprinichthys').extinct() # from GBIF

    # 2015-09-11 https://github.com/OpenTreeOfLife/feedback/issues/82
    ott.taxon('Tarsius thailandica').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/86
    ott.taxon('Gillocystis').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/186
    # https://en.wikipedia.org/wiki/Réunion_ibis
    thres = ott.taxon('Threskiornis solitarius') # from GBIF
    thres.absorb(ott.taxon('Raphus solitarius')) # from GBIF
    thres.extinct()

    # https://github.com/OpenTreeOfLife/feedback/issues/282
    ott.taxon('Chelomophrynus', 'Anura').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/283
    ott.taxon('Shomronella', 'Anura').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/165
    sphe = False
    for child in ott.taxon('Sphenodontidae').children: # from GBIF
        if child.name != 'Sphenodon':
            child.extinct()
        else:
            sphe = True
    if not sphe:
        print '** No extant member of Sphenodontidae'

    # https://github.com/OpenTreeOfLife/feedback/issues/159
    # sez: 'The order Soricomorpha ("shrew-form") is a taxon within the
    # class of mammals. In previous years it formed a significant group
    # within the former order Insectivora. However, that order was shown
    # to be polyphyletic ...'
    ott.taxon('Nesophontidae', 'Soricomorpha').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/135
    ott.taxon('Cryptobranchus matthewi', 'Amphibia').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/134
    ott.taxon('Hemitrypus', 'Amphibia').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/133
    ott.taxon('Cordicephalus', 'Amphibia').extinct() # from GBIF

    # https://github.com/OpenTreeOfLife/feedback/issues/123
    ott.taxon('Gryphodobatis', 'Orectolobidae').extinct() # from GBIF

    # Recover missing extinct flags.  I think these are problems in
    # the dump that I have, but have been fixed in the current IRMNG
    # (July 2016).
    for (name, super) in [
            ('Tvaerenellidae', 'Ostracoda'),
            ('Chrysocythere', 'Ostracoda'),
            ('Mutilus', 'Ostracoda'),
            ('Aurila', 'Ostracoda'),
            ('Loxostomum', 'Ostracoda'),
            ('Loxostomatidae', 'Ostracoda'),
    ]:
        if super == None:
            tax = ott.maybeTaxon(name) # IRMNG
        else:
            tax = ott.maybeTaxon(name, super)
        if tax != None: tax.extinct()

    # https://github.com/OpenTreeOfLife/feedback/issues/304
    ott.taxon('Notobalanus', 'Maxillopoda').extant() # IRMNG

    # https://github.com/OpenTreeOfLife/feedback/issues/303
    ott.taxon('Neolepas', 'Maxillopoda').extant() # IRMNG

    # See NCBI
    ott.taxon('Millericrinida').extant() # WoRMS



# The processed GBIF taxonomy contains a file listing GBIF taxon ids for all
# taxa that are listed as coming from PaleoDB.  This is processed after all
# taxonomies are processed but before patches are applied.  We use it to set
# extinct flags for taxa originating only from GBIF (i.e. if the taxon also
# comes from NCBI, WoRMS, etc. then we do not mark it as extinct).

def get_default_extinct_info_from_gbif(gbif, gbif_to_ott):
    infile = open('tax/gbif/paleo.tsv')
    paleos = 0
    flagged = 0
    for row in infile:
        paleos += 1
        id = row.strip()
        gtaxon = gbif.lookupId(id)
        if gtaxon != None:
            taxon = gbif_to_ott.image(gtaxon)
            if taxon != None:
                if taxon.sourceIds[0].prefix == 'gbif':
                    # See https://github.com/OpenTreeOfLife/feedback/issues/43
                    # It's OK if it's also in IRMNG
                    flagged += 1
                    taxon.extinct()
    infile.close()
    print '| Flagged %s of %s taxa from paleodb\n' % (flagged, paleos)

def unextinct_ncbi(ncbi, ncbi_to_ott):
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/68
    # 'Extinct' would really mean 'extinct and no sequence' with this change
    print 'Non-extincting NCBI'

    def recur(node):
        unode = ncbi_to_ott.image(node)
        if node.children == None:
            if unode == None:
                return True
            else:
                return unode.isAnnotatedExtinct()
        else:
            inct = True
            for child in node.children:
                inct = inct and recur(child)
            if not inct:
                if unode != None and unode.isAnnotatedExtinct():
                    # Contains a possibly extant descendant...
                    print '* Changing from extinct to extant because in NCBI', unode.name, unode.id
                    unode.extant()
                return False
            else:
                return True

    for node in ncbi.roots():
        recur(node)


# Reports

def report_on_h2007(h2007, h2007_to_ott):
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/40
    print '-- Checking realization of h2007'
    for taxon in h2007.taxa():
        im = h2007_to_ott.image(taxon)
        if im != None:
            if im.children == None:
                print '** Barren taxon from h2007', taxon.name
        else:
            print '** Missing taxon from h2007', taxon.name

def report(ott):

    if False:
        # This one is getting too big.  Should write it to a file.
        print '-- Parent/child homonyms'
        ott.parentChildHomonymReport()

    # Requires ../germinator
    print '-- Inclusion tests'
    check_inclusions.check(inclusions_path, ott)
    # tests deleted because taxon no longer present:
    #  Progenitohyus,Cetartiodactyla,3615889,"https://github.com/OpenTreeOfLife/feedback/issues/58"
    #  Protaspis,Opisthokonta,5345086,"not found"
    #  Coscinodiscus,Porifera,5344432,""
    #  Retaria,Opisthokonta,5297815,""
    #  Campanella,Holozoa,5343447,""
    #  Hessea,Holozoa,5295839,""
    #  Neoptera,Tachinidae,5340261,"test of genus"

names_of_interest = ['Ciliophora',
                     'Phaeosphaeria',
                     'Morganella',
                     'Saccharomycetes',

                     # From the deprecated file
                     'Methanococcus maripaludis',
                     'Cyanidioschyzon',
                     'Pseudoalteromonas atlantica',
                     'Pantoea ananatis', # deprecated and gone
                     'Gibberella zeae', # was deprecated

                     # From notSame directives
                     'Acantharia', # in Venturiaceae < Fungi < Opisth. / Rhizaria < SAR
                     'Steinia', # in Lecideaceae < Fungi / Alveolata / insect < Holozoa in irmng
                     'Epiphloea', # in Pezizomycotina < Opisth. / Rhodophyta  should be OK, Rh. is a division
                     'Campanella', # in Agaricomycotina < Nuclet. / SAR / Holozoa  - check IF placement
                     'Lacrymaria', # in Agaricomycotina / ?
                     'Frankia',    # in Pezizomycotina / Bacteria
                     'Phialina',   # in Pezizomycotina
                     'Bogoriella',

                     'Bostrychia',
                     'Buchnera',
                     'Podocystis', # not found
                     'Crepidula',
                     'Hessea',
                     'Choanoflagellida',
                     'Choanozoa',
                     'Retaria',
                     'Labyrinthomorpha',
                     'Ophiurina',
                     'Rhynchonelloidea',
                     'Neoptera',
                     'Tipuloidea',
                     'Tetrasphaera',
                     'Protaspis',
                     'Coscinodiscus',
                     'Photorhabdus luminescens', # samples from deprecated list
                     'Xenorhabdus bovienii',
                     'Gibberella zeae',
                     'Ruwenzorornis johnstoni',
                     'Burkea',

                     'Blattodea',
                     'Eumetazoa',
                     'Bivalvia',
                     'Pelecypoda',
                     'Parmeliaceae',
                     'Heterolepa',
                     'Acanthokara',
                     'Epigrapsus notatus',  # occurs twice in worms, should be merged...
                     'Carduelis barbata',  # 'incompatible-use'
                     'Spinus barbatus',
                     'Abatia',
                     'Jungermanniaceae',
                     'Populus deltoides',
                     'Salicaceae',
                     'Salix sericea',
                     'Streptophytina',
                     'Loxosporales',
                     'Sarrameanales',
                     'Trichoderma',
                     'Hypocrea',
                     'Elaphocordyceps subsessilis', # incompatible-use - ok
                     'Bacillus selenitireducens',   # incompatible-use
                     'Nematostella vectensis',
                     'Aiptasia pallida',  # Cyanobacteria / cnidarian confusion
                     'Mahonia',  # merged
                     'Maddenia', # merged
                     'Crenarchaeota', # silva duplicate
                     'Dermabacter',
                     'Orzeliscidae', # should be 'rejected refinement'
                     'Sogonidae',
                     'Echinochalina',
                     'Callyspongia elegans',
                     'Callyspongia',
                     'Pseudostomum',
                     'Pseudostomidae',
                     'Parvibacter',
                     'Euxinia',
                     'Xiphonectes',
                     'Cylindrocarpon',
                     'Macrophoma',
                     'Tricellulortus peponiformis',
                     'Dischloridium',
                     'Gloeosporium',
                     'Exaiptasia pallida',
                     'Cladochytriaceae',
                     'Hyaloraphidium',
                     'Marssonina',
                     'Marssonia',
                     'Platypus',
                     'Dendrosporium',
                     'Diphylleia',
                     'Myzostomida',
                     'Endomyzostoma tenuispinum',
                     'Myzostoma cirriferum',
                     'Helotiales',
                     'Leotiales',
                     'Desertella',
                     'Cyclophora',
                     'Pohlia',
                     'Lonicera',
                     ]
