### Author: Edward Huang

import numpy as np
from collections import OrderedDict
from scipy.stats import fisher_exact
import operator
import sys

### Gets the top pathways for each drug/cell-line using the LINCS data set.
### Usage: python top_pathways_lincs.py AFT_NUM

Z_SCORE_MIN = 2
MAX_GENES_PER_DRUG = 250
LOW_P_THRESHOLD = 0.0001 # Count how many pathway-drug pairs are below this.

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: %s AFT-NUM' % sys.argv[0]
        exit()
    aft_num = sys.argv[1]

    # Define -infinity
    inf = float('-inf')

    print 'Extracting NCI pathways...'
    # Dictionary, keys=path names, values=genes in pathway
    nci_path_dct = OrderedDict({})
    # A set of all of the genes over all NCI pathways.
    nci_genes = set([])

    path_file = open('./data/nci_pathway_hgnc.txt', 'r')
    for line in path_file:
        path_name, path_gene = line.strip().split('\t')
        nci_genes.add(path_gene)
        if path_name in nci_path_dct:
            nci_path_dct[path_name] += [path_gene]
        else:
            nci_path_dct[path_name] = [path_gene]
    path_file.close()

    # Extract genes from all_map.txt, provided by Sheng.
    f = open('./data/all_map.txt', 'r')
    genes = []
    for i, line in enumerate(f):
        line = line.split()
        # The rows are sorted by genes, and all LINCS data have the same order
        # of genes as the level 3 data.
        genes += [line[1]]
    f.close()

    print 'Extracting LINCS data...'
    f = open('./data/lvl4_Stuart_combinedPvalue_Aft_%s.txt' % aft_num, 'r')
    drugs = []
    gene_dct = OrderedDict({})
    for i, line in enumerate(f):
        line = line.split()
        gene = genes[i - 1]
        if i == 0:
            # Take out the lvl4_ prefix
            drugs = [raw_string[len('lvl4_'):] for raw_string in line]
        elif gene == '-666':
            continue
        else:
            # #NAME? is negative infinity in the excel file.
            z_scores = [inf if x == '#NAME?' else abs(float(x)) for x in line]
            if gene not in gene_dct:
                gene_dct[gene] = z_scores
            else:
                # If a gene appears twice, then we want to get the max values.
                for ci, value in enumerate(z_scores):
                    gene_dct[gene][ci] = max(gene_dct[gene][ci], value)
    f.close()
    
    # Update genes to be just the valid ones in our dictionary.
    genes = gene_dct.keys()

    print 'Cleaning data and converting to dictionary...'
    drug_matrix = [drugs]
    for gene in gene_dct:
        drug_matrix += [gene_dct[gene]]
    gene_dct.clear()
    drug_matrix = np.array(drug_matrix).transpose()

    print 'Creating new z-score dictionary...'
    # Change names of the drug ID's to English drug names.
    temp_drug_matrix = OrderedDict({})
    # Make a new dictionary, with keys as drugs, and values as lists of LINCS
    # z-scores.
    for i, row in enumerate(drug_matrix):
        raw_string = row[0].split('_')
        drug, cell_line = raw_string[0], raw_string[1]

        ### Mayo data translation.
        drug, z_scores = drug + '_' + cell_line, row[1:]

        # Convert to floats again because np.transpose() changes to strings.
        z_scores = map(float, z_scores)

        if drug in temp_drug_matrix:
            temp_drug_matrix[drug] += [z_scores]
        else:
            temp_drug_matrix[drug] = [z_scores]
    drug_matrix = temp_drug_matrix

    for drug in drug_matrix:
        z_scores = drug_matrix[drug]
        # Average the z-scores for different experiments of the same drug-cell
        # line pair.
        z_scores = [np.mean(x) for x in zip(*z_scores)]
        top_gene_indices = []
        for i, z_score in enumerate(z_scores):
            if z_score >= Z_SCORE_MIN:
                top_gene_indices += [(i, z_score)]
        # Take only at most MAX_GENES_PER_DRUG.
        top_gene_indices = sorted(top_gene_indices, key=lambda k:k[1],
            reverse=True)[:MAX_GENES_PER_DRUG]
        top_genes = [genes[i] for i, z_score in top_gene_indices]
        drug_matrix[drug] = top_genes

    out = open('./results/top_pathways_lincs_Aft_%s_hgnc.txt' % aft_num, 'w')
    # Fisher's test for every drug/cell-line and path pair.
    total_num_genes = len(nci_genes.union(genes))
    fish_dct = {}
    num_low_p = 0
    for drug in drug_matrix:
        # Genes with the top z-scores for each drug, up to MAX_GENES_PER_DRUG.
        corr_genes = set(drug_matrix[drug])
        for path in nci_path_dct:
            path_genes = set(nci_path_dct[path])

            # Get the four relevant numbers for Fisher's test.
            corr_and_path = len(corr_genes.intersection(path_genes))
            corr_not_path = len(corr_genes.difference(path_genes))
            path_not_corr = len(path_genes.difference(corr_genes))
            neither = total_num_genes - len(corr_genes.union(path_genes))
            # Compute Fisher's test.
            o_r, p_value = fisher_exact([[corr_and_path, corr_not_path],
                [path_not_corr, neither]])
            if p_value < LOW_P_THRESHOLD:
                num_low_p += 1
            fkey = (drug, path, corr_and_path, corr_not_path, path_not_corr)
            fish_dct[fkey] = p_value
    sorted_fisher = sorted(fish_dct.items(), key=operator.itemgetter(1))
    # Write how many drug-pathway pairs have a very low p-value, determined by
    # LOW_P_THRESHOLD.
    out.write('num_p_below_%s\t%d\n' % (str(LOW_P_THRESHOLD), num_low_p))
    # Write the drug's top pathways to file.
    out.write('drug\tcell_line\tpath\tp-value\tinter\tlincs\tpath\n')
    for fkey, score in sorted_fisher:
        drug, path, inter, corr_len, path_len = fkey
        drug, cell_line = drug.split('_')
        out.write('%s\t%s\t%s\t' % (drug, cell_line, path))
        out.write('%g\t%d\t%d\t%d\n' % (score, inter, corr_len, path_len))
    out.close()