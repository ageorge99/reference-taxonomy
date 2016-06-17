# Jython script to build the Open Tree reference taxonomy
# coding=utf-8

# Unless specified otherwise issues are in the reference-taxonomy repo:
# https://github.com/OpenTreeOfLife/reference-taxonomy/issues/...

import sys

from org.opentreeoflife.taxa import Taxonomy, SourceTaxonomy, TsvEdits
from org.opentreeoflife.smasher import UnionTaxonomy
from ncbi_ott_assignments import ncbi_assignments_list
sys.path.append("feed/misc/")
from chromista_spreadsheet import fixChromista
import taxonomies
import check_inclusions
from claim import Has_child, test_claims
import csv

this_source = 'https://github.com/OpenTreeOfLife/reference-taxonomy/blob/master/make-ott.py'
inclusions_path = '../germinator/taxa/inclusions.csv'

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
        ott.eventlogger.namesOfInterest.add(name)

    # When lumping, prefer to use ids that have been used in OTU matching
    # This list could be used for all sorts of purposes...
    ott.loadPreferredIds('ids-that-are-otus.tsv', False)
    ott.loadPreferredIds('ids-in-synthesis.tsv', True)

    # idspace string 'skel' is magical, see Taxon.addSource
    ott.setSkeleton(Taxonomy.getTaxonomy('tax/skel/', 'skel'))

    # This is a particularly hard case; create alignment targets up front
    deal_with_ctenophora(ott)

    # SILVA
    silva = taxonomies.load_silva()
    ott.absorb(silva, align_silva(silva, ott))
    check_invariants(ott)

    # Hibbett 2007
    h2007 = taxonomies.load_h2007()
    ott.absorb(h2007)

    # Index Fungorum
    (fungi, fungorum_sans_fungi) = split_fungorum(ott)
    ott.absorb(fungi, align_fungi(fungi, ott))
    check_invariants(ott)

    # the non-Fungi from Index Fungorum get absorbed below

    lamiales = taxonomies.load_713()
    ott.absorb(lamiales, align_lamiales(lamiales, ott))

    # WoRMS
    (malacostraca, worms_sans_malacostraca) = split_worms(ott)
    ott.absorb(malacostraca)

    # NCBI
    ncbi = taxonomies.load_ncbi()

    # Get SILVA cluster / NCBI id correspondence.
    mappings = ncbi_to_silva(ncbi, silva, ott)

    ott.absorb(ncbi, align_ncbi(ncbi, silva, ott))
    check_invariants(ott)

    compare_ncbi_to_silva(mappings, ott)

    # WoRMS
    worms_sans_malacostraca.taxon('Biota').synonym('life')
    # This is suboptimal, but the names are confusing the division logic
    worms_sans_malacostraca.taxon('Glaucophyta'). \
        absorb(worms_sans_malacostraca.taxon('Glaucophyceae'))
    a = align_worms(worms_sans_malacostraca, ott)
    ott.absorb(worms_sans_malacostraca, a)

    # The rest of Index Fungorum (maybe not a good idea)
    ott.absorb(fungorum_sans_fungi)

    # GBIF
    gbif = taxonomies.load_gbif()
    ott.absorb(gbif, align_gbif(gbif, ott))

    # IRMNG
    irmng = taxonomies.load_irmng()
    ott.absorb(irmng, align_irmng(irmng, ott))

    taxonomies.link_to_h2007(ott)

    get_default_extinct_info_from_gbif(gbif, ott)

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
            ('Gloeosporium', 'Pezizomycotina', '75019'),
            ('Escherichia coli', 'Enterobacteriaceae', '474506'), # ncbi:562
            # ('Dischloridium', 'Trichocomaceae', '895423'),
    ]:
        tax = ott.maybeTaxon(inf, sup)
        if tax != None:
            tax.setId(id)

    ott.taxon('474506

    ott.taxonThatContains('Rhynchonelloidea', 'Sphenarina').setId('795939') # NCBI

    for (ncbi_id, ott_id, name) in ncbi_assignments_list:
        n = ncbi.maybeTaxon(ncbi_id)
        if n != None:
            im = ott.image(n)
            if im != None:
                im.setId(ott_id)
            else:
                print '** NCBI %s not mapped - %s' % (ncbi_id, name)
        else:
            print '** No NCBI taxon %s - %s' % (ncbi_id, name)

    # Cylindrocarpon is now Neonectria
    ott.image(gbif.taxon('2563163')).setId('51754')

    # Trichosporon is a mess, because it occurs 3 times in NCBI.
    trich = ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum')
    if trich != None:
        trich.setId('364222')

    #ott.image(fungi.taxon('11060')).setId('4107132') #Cryptococcus - a total mess

    # OTT 2.9 has both Glaucophyta and Glaucophyceae... bad news
    # Need to review this
    g1 = ids.maybeTaxon('Glaucophyta')
    g2 = ids.maybeTaxon('Glaucophyceae')
    if g1 != None and g2 != None and g1 != g2:
        g1.absorb(g2)


    # --------------------
    # Assign OTT ids to taxa that don't have them, re-using old ids when possible
    ids = Taxonomy.getTaxonomy('tax/prev_ott/', 'ott')

    # Kludge to undo lossage in OTT 2.9
    for taxon in ids.taxa():
        if (len(taxon.sourceIds) >= 2 and
            taxon.sourceIds[0].prefix == "ncbi" and
            taxon.sourceIds[1].prefix == "silva"):
            taxon.sourceIds.remove(taxon.sourceIds[0])

    # Assign old ids to nodes in the new version
    ott.assignIds(ids, 'additions')

    ott.check()

    report_on_h2007(h2007, ott)

    return ott

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

    ctenophora_diatom = establish('Ctenophora', ott,
                                  ancestor='Bacillariophyta',
                                  ott_id='103964')

    # The comb jelly should already be in skeleton, but include the code for symmetry.
    ctenophora_jelly = establish('Ctenophora', ott,
                                 parent='Metazoa',
                                 ott_id='641212')

    # The fly will be added by NCBI; provide a node to map it to.
    ctenophora_fly = establish('Ctenophora', ott,
                               division='Arthropoda',
                               ott_id='1043126')

    establish('Podocystis', ott, division='Fungi', ott_id='809209')
    establish('Podocystis', ott, parent='Bacillariophyta', ott_id='357108')


# ----- SILVA -----

def align_silva(silva, ott):
    a = ott.alignment(silva)
    a.same(silva.taxonThatContains('Ctenophora', 'Ctenophora pulchella'),
           ott.taxon('103964'))
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
            print 'no %s in IF' % name # 'no Acantharia in IF'
        elif True:
            a.same(tax1, establish(name, ott, ancestor=f))
        else:
            # ### CHECK: was silva.taxon
            tax2 = ott.taxon(name, o)
            # disable all notSames
            if tax1 == None:
                print 'no %s in IF' % name # 'no Acantharia in IF'
                if tax1 != None and tax2 != None and tax == None:
                    # Import tax1 into ott under Fungi.  Similar to
                    # Ctenophora case.
                    # tax = ott.newTaxon(name, tax1.rank, tax1.getQualifiedId())
                    # ott.taxon(f).take(tax)
                    # tax.incertaeSedis()
                    # ott.same(tax1, tax)
                    a.notSame(tax1, tax2)
                    # Trichoderma harzianum, Sclerotinia homoeocarpa, Puccinia
                    # triticina are removed from SILVA early
                elif tax2 == None:
                    print 'no %s in OTT' % name
                    
    # 2014-04-25 JAR
    # There are three Bostrychias: a rhodophyte, a fungus, and a bird.
    # The fungus name is a synonym for Cytospora.
    # ### CHECK: was silva.taxon
    if fungi.maybeTaxon('Bostrychia', 'Ascomycota') != None:
        if do_notSames:
            a.notSame(fungi.taxon('Bostrychia', 'Ascomycota'),
                      ott.taxon('Bostrychia', 'Rhodophyceae'))
        else:
            fungi.removeFromNameIndex(fungi.taxon('Bostrychia', 'Ascomycota'), 'Bostrychia')

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
    if False:
        a.same(fungorum.maybeTaxon('Choanoflagellida'),
               ott.maybeTaxon('Choanoflagellida', 'Opisthokonta'))

    return a

# ----- Lamiales taxonomy from study 713 -----
# http://dx.doi.org/10.1186/1471-2148-10-352

def align_lamiales(study713, ott):
    a = ott.alignment(study713)
    # ### CHECK: was silva.taxon
    if do_notSames:
        a.notSame(study713.taxon('Buchnera', 'Orobanchaceae'), ott.taxon('Buchnera', 'Enterobacteriaceae'))
    return a

# ----- WoRMS -----

def split_worms(ott):
    worms = taxonomies.load_worms()
    # Malacostraca instead of Decapoda because M. is in the skeleton
    mal = worms.taxon('Malacostraca')
    malacostraca = worms.select(mal)
    mal.trim()
    worms_sans_malacostraca = worms
    return (malacostraca, worms_sans_malacostraca)

# ----- NCBI Taxonomy -----

def align_ncbi(ncbi, silva, ott):

    a = ott.alignment(ncbi)

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

    # https://github.com/OpenTreeOfLife/feedback/issues/45
    # This shouldn't be needed any more now that the Ichthyosporea one
    # is pruned.
    if do_notSames:
        a.notSame(ncbi.maybeTaxon('Choanoflagellida', 'Opisthokonta'),
                  ott.maybeTaxon('Choanoflagellida', 'Ichthyosporea'))

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

    return a

# Maps taxon in NCBI taxonomy to SILVA-derived OTT taxon

def ncbi_to_silva(ncbi, silva, ott):
    mappings = {}
    flush = []
    with open('feed/silva/out/ncbi_to_silva.tsv', 'r') as infile:
        reader = csv.reader(infile, delimiter='\t')
        for (ncbi_id, silva_cluster_id) in reader:
            n = ncbi.maybeTaxon(ncbi_id)
            if n != None:
                s = silva.maybeTaxon(silva_cluster_id)
                if s != None:
                    so = ott.image(s)
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
                    print '| no such cluster', silva_cluster_id
    for n in flush:
        if n in mappings:
            del mappings[n]
    return mappings

def compare_ncbi_to_silva(mappings, ott):
    problems = 0
    for taxon in mappings:
        t1 = mappings[taxon]
        t2 = ott.image(taxon)
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
    a.same(worms.taxonThatContains('Trichosporon', 'Trichosporon lodderae'),
           ott.taxonThatContains('Trichosporon', 'Trichosporon cutaneum'))
    a.same(worms.taxonThatContains('Trichoderma', 'Trichoderma koningii'),
           ott.taxonThatContains('Trichoderma', 'Trichoderma koningii'))
    return a

# ----- GBIF (Global Biodiversity Information Facility) taxonomy -----

def align_gbif(gbif, ott):

    a = ott.alignment(gbif)

    gbif.taxon('Viruses').hide()

    # Fungi suppressed at David Hibbett's request
    gbif.taxon('Fungi').hideDescendantsToRank('species')

    # Suppressed at Laura Katz's request
    gbif.taxon('Bacteria','life').hideDescendants()
    gbif.taxon('Archaea','life').hideDescendants()

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

    return a

# ----- Interim Register of Marine and Nonmarine Genera (IRMNG) -----

def align_irmng(irmng, ott):

    a = ott.alignment(irmng)

    # irmng.taxon('Viruses').hide()  see taxonomies.py

    # Fungi suppressed at David Hibbett's request
    irmng.taxon('Fungi').hideDescendantsToRank('species')

    # Microbes suppressed at Laura Katz's request
    irmng.taxon('Bacteria','life').hideDescendants()
    irmng.taxon('Archaea','life').hideDescendants()

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


    # JAR 2014-04-24 false match
    # IRMNG has one in Pteraspidomorphi (basal Chordate) as well as a
    # protozoan (SAR; ncbi:188977).
    a.notSame(irmng.taxon('Protaspis', 'Chordata'),
              ott.taxon('Protaspis', 'Cercozoa'))

    # JAR 2014-04-18 while investigating hidden status of Coscinodiscus radiatus.
    # tests
    a.notSame(irmng.taxon('Coscinodiscus', 'Porifera'),
              ott.taxon('Coscinodiscus', 'Stramenopiles'))

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

    # 2015-09-10 Inclusion test failing
    a.notSame(irmng.taxon('Retaria', 'Brachiopoda'), # irmng:1340611
                ott.taxon('Retaria', 'Rhizaria'))

    # 2015-09-10 Inclusion test failing
    a.notSame(irmng.taxon('Campanella', 'Cnidaria'), # irmng:1289625
                ott.taxon('Campanella', 'SAR'))

    a.same(irmng.taxonThatContains('Trichoderma', 'Trichoderma koningii'),
           ott.taxonThatContains('Trichoderma', 'Trichoderma koningii'))

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
    ott.taxon('Chlamydotomus').incertaeSedis()

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
    ott.taxon('Adlerocystis').incertaeSedis()

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

    print '-- more patches --'

    # From Laura and Dail on 5 Feb 2014
    # https://groups.google.com/d/msg/opentreeoflife/a69fdC-N6pY/y9QLqdqACawJ
    tax = ott.maybeTaxon('Chlamydiae/Verrucomicrobia group')
    if tax != None and tax.name != 'Bacteria':
        tax.rename('Verrucomicrobia group')
    # The following is obviated by algorithm changes
    # ott.taxon('Heterolobosea','Discicristata').absorb(ott.taxon('Heterolobosea','Percolozoa'))
    ott.taxon('Excavata','Eukaryota').take(ott.taxon('Oxymonadida','Eukaryota'))

    # There is no Reptilia in OTT 2.9, so this can probably be deleted
    if ott.maybeTaxon('Reptilia') != None:
        ott.taxon('Reptilia').hide()

    # Chris Owen patches 2014-01-30
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/88
    ott.taxon('Protostomia').take(ott.taxonThatContains('Chaetognatha','Sagittoidea'))
    ott.taxon('Lophotrochozoa').take(ott.taxon('Platyhelminthes'))
    ott.taxon('Polychaeta','Annelida').take(ott.taxon('Myzostomida'))
    ott.taxon('Lophotrochozoa').take(ott.taxon('Gnathostomulida'))
    ott.taxon('Bilateria').take(ott.taxon('Acoela'))
    ott.taxon('Bilateria').take(ott.taxon('Xenoturbella'))
    ott.taxon('Bilateria').take(ott.taxon('Nemertodermatida'))
    # https://dx.doi.org/10.1007/s13127-011-0044-4
    # Not in deuterostomes
    ott.taxon('Bilateria').take(ott.taxon('Xenacoelomorpha'))
    if ott.maybeTaxon('Staurozoa') == None:
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
        tax = ott.maybeTaxon(name)
        if tax != None:
            tax.extinct()

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

    # "Old" patch system
    TsvEdits.edit(ott, 'feed/ott/edits/')

    # This is a randomly chosen bivalve to force Bivalvia to not be extinct
    ott.taxon('Corculum cardissa', 'Bivalvia').extant()
    # Similarly for roaches
    ott.taxon('Periplaneta americana', 'Blattodea').extant()

def get_default_extinct_info_from_gbif(gbif, ott):
    infile = open('tax/gbif/paleo.tsv')
    paleos = 0
    flagged = 0
    for row in infile:
        paleos += 1
        id = row.strip()
        gtaxon = gbif.lookupId(id)
        if gtaxon != None:
            taxon = ott.image(gtaxon)
            if taxon != None:
                if len(taxon.sourceIds) == 1:
                    flagged += 1
                    taxon.extinct()
    infile.close()
    print '| Flagged %s of %s taxa from paleodb\n' % (flagged, paleos)

def unextinct_ncbi(ncbi, ott):
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/68
    # 'Extinct' would really mean 'extinct and no sequence' with this change
    print 'Non-extincting NCBI'

    def recur(node):
        unode = ott.image(node)
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
                    print 'Changing from extinct to extant', unode.name, unode.id
                    unode.extant()
                return False
            else:
                return True

    for node in ncbi.roots():
        recur(node)


# Reports

def report_on_h2007(h2007, ott):
    # https://github.com/OpenTreeOfLife/reference-taxonomy/issues/40
    print '-- Checking realization of h2007'
    for taxon in h2007.taxa():
        im = ott.image(taxon)
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
                     ]

def establish(name, taxonomy, rank=None, descendant=None, parent=None, ancestor=None, division=None, ott_id=None, source=None):
    taxon = None
    if descendant != None and taxonomy.lookup(descendant) != None:
        taxon = taxonomy.taxonThatContains(name, descendant)
    anc = None
    if parent != None:
        if taxonomy.unique(parent) != None: anc = parent
        taxon2 = taxonomy.maybeTaxon(name, parent)
        if taxon2 != None:
            if taxon != None and taxon2 != taxon:
                print '** conflicting taxon determination (parent)', taxon, taxon2, parent
            else:
                taxon = taxon2
    if ancestor != None:
        if anc == None and taxonomy.unique(ancestor) != None: anc = ancestor
        taxon2 = taxonomy.maybeTaxon(name, ancestor)
        if taxon2 != None:
            if taxon != None and taxon2 != taxon:
                print '** conflicting taxon determination (ancestor)', taxon, taxon2, ancestor
            else:
                taxon = taxon2
    if division != None:
        if anc == None and taxonomy.unique(division) != None: anc = division
        taxon2 = taxonomy.maybeTaxon(name, division)
        if taxon2 != None:
            if taxon != None and taxon2 != taxon:
                print '** conflicting taxon determination (division)', taxon, taxon2, division
            else:
                taxon = taxon2
    if ott_id != None:
        ott_id = str(ott_id)
        taxon2 = taxonomy.maybeTaxon(ott_id)
        if taxon2 != None:
            if taxon != None and taxon2 != taxon:
                print '** conflicting taxon determination (id)', taxon, taxon2, ott_id
            else:
                taxon = taxon2
        elif taxon != None and taxon.id == None:
            print '** could set if of %s to %s', taxon, ott_id
    if taxon == None:
        taxon = taxonomy.newTaxon(name, rank, source)
        if anc != None:
            taxonomy.taxon(anc).take(taxon)
        else:
            print '** no ancestor to attach new node to', name
        if ott_id != None:
            taxon.setId(ott_id)
        if anc != parent:
            taxon.incertaeSedis()
    return taxon

