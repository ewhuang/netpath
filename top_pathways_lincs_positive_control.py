### Author: Edward Huang

import numpy as np
from collections import OrderedDict
from scipy.stats import fisher_exact
import operator
import sys

### Gets the top pathways for each drug/cell-line using the LINCS data set with
### positive control on the drug MYC. This is used to verify if the LINCS data
### is correct. Takes in one argument, the suffix number for Aft_num.

Z_SCORE_MIN = 2
MAX_GENES_PER_DRUG = 500
LOW_P_THRESHOLD = 1e-04 # Count how many pathway-drug pairs are below this.

### Create new list copy without duplicates.
def create_no_dup(lst):
    new_lst = []
    for e in lst:
        if e not in new_lst:
            new_lst.append(e)
    return new_lst

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: %s AFT-NUM' % sys.argv[0]
        exit()
    aft_num = sys.argv[1]

    # Create dictionary, keys are drug ID's, values are the English drug names.
    f = open('./data/drug_translation.txt', 'r')
    trans_dct = {}
    for line in f:
        drug_name, drug_id = line.split()
        trans_dct[drug_id] = drug_name

    print 'Extracting NCI pathways...'
    path_file = open('./data/nci_pathway.txt', 'r')
    # nci_path_dct, keys are NCI pathway names, values are lists of genes in the
    # corresponding pathways.
    nci_path_dct = {}
    # A set of all of the genes over all NCI pathways.
    nci_genes = set([])
    for line in path_file:
        line = line.strip().split('\t')
        path_name, path_gene = line[0], line[1]

        nci_genes.add(path_gene)
        
        if path_name not in nci_path_dct:
            nci_path_dct[path_name] = [path_gene]
        else:
            nci_path_dct[path_name] += [path_gene]
    path_file.close()

    # Extract genes from LINCS level 3
    f = open('./data/lincs_zscore.txt', 'r')
    genes = []
    for i, line in enumerate(f):
        if i == 0:
            continue
        line = line.split()
        genes += [line[1]]
    f.close()

    print 'Extracting LINCS data...'
    f = open('./data/lvl4_combinedPvalue_positive_control_Aft_%s.txt' % aft_num, 'r')
    drugs = []
    gene_dct = OrderedDict({})
    # Define -infinity
    inf = float('-inf')
    for i, line in enumerate(f):
        line = line.split()
        gene = genes[i-1]
        if i == 0:
            # Take out the lvl4_ prefix
            drugs = [raw_string[5:] for raw_string in line]
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
    drug_matrix = np.array(drug_matrix).transpose()

    # Change names of the drug ID's to English drug names.
    temp_drug_matrix = OrderedDict({})
    # Make a new dictionary, with keys as drugs, and values as lists of LINCS
    # z-scores.
    for i, row in enumerate(drug_matrix):
        raw_string = row[0].split('_')
        drug, cell_line = raw_string[0], raw_string[1]
        drug, z_scores = drug + '_' + cell_line, row[1:]#trans_dct[drug] + '_' + cell_line, row[1:]
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

    out = open('./results/top_pathways_lincs_positive_control_Aft_%s.txt' % aft_num, 'w')
    # Fisher's test for every drug/cell-line and path pair.
    total_num_genes = len(nci_genes.union(genes))
    fish_dct = {}
    num_low_p = 0
    for drug in drug_matrix:
        for path_index, path in enumerate(nci_path_dct):
            path_genes = set(nci_path_dct[path])
            n = len(path_genes)
            corr_genes = set(drug_matrix[drug])
            corr_and_path = len(corr_genes.intersection(path_genes))
            corr_not_path = len(corr_genes.difference(path_genes))
            path_not_corr = len(path_genes.difference(corr_genes))
            neither = total_num_genes - len(corr_genes.union(path_genes))
            o_r, p_value = fisher_exact([[corr_and_path, corr_not_path],
                [path_not_corr, neither]])
            if p_value < LOW_P_THRESHOLD:
                num_low_p += 1
            fish_dct[(drug, path, corr_and_path, len(corr_genes), n)] = p_value
    sorted_fisher = sorted(fish_dct.items(), key=operator.itemgetter(1))
    # Write the drug's top pathways to file.
    out.write('num_p_below_%s\t%d\n' % (str(LOW_P_THRESHOLD), num_low_p))
    out.write('drug\tcell_line\tpath\tp-value\tinter\tlincs\tpath\n')
    for info, score in sorted_fisher:
        drug, path, inter, corr_len, path_len = info
        drug, cell_line = drug.split('_')
        out.write('%s\t%s\t%s\t' % (drug, cell_line, path))
        out.write('%g\t%d\t%d\t%d\n' % (score, inter, corr_len, path_len))
    out.close()