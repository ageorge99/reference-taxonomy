package org.opentreeoflife.taxa;

public class Synonym extends Node {

    // name inherited from class Node

    String type;                 // synonym, authority, common name, etc.

    public Synonym(String name, String type, Taxon taxon) {
        super(name);
        this.parent = taxon;
        this.type = type;
        taxon.taxonomy.addToNameIndex(this, name);
    }

    public Taxon taxon() { return parent; }

    public Taxonomy getTaxonomy() { return parent.taxonomy; }

    public boolean taxonNameIs(String othername) {
        return parent.name.equals(othername);
    }

    public String uniqueName() {
        String uniq = parent.uniqueName();
        if (uniq.length() == 0) uniq = parent.name;
        return String.format("%s (synonym for %s)", this.name, uniq);
    }

}
