import unittest
import os
from fgcz_biobeamer import BioBeamer
import time

class TestFileFilter(unittest.TestCase):
    """
    run
        python -m unittest -v fgcz_biobeamer

    """
    folder = "/Users/witold/test2"
    outfolder = "/Users/witold/out2"

    def test_tripletoff(self):
        print("hello world")
        time.sleep(5)
        BB = BioBeamer(
            source_path = self.folder,
            target_path = self.outfolder
        )
        BB.set_para('min_time_diff', 10)
        BB.set_para('pattern', ".+\.raw")
        BB.set_para('simulate', True)
        BB.print_para()
        BB.run()

    def fileList(self):
        res = [["p1000/Proteomics/FUSION_1/pgehrig_20150526_TiO2_NH3_Pyr/20150526_10_fetuin_40fmol.raw", 240522870, 1432711212],
        ["p1000/Proteomics/FUSION_1/pgehrig_20150602_30PP_CE/20150602_02_30PP_400fmol.raw", 411759072, 1433346022],
        ["p1000/Proteomics/QEXACTIVEHF_1/tobiasko_20150526/20150526_12_400amol_fetuin_incl_iRT_1in800.raw", 196057154, 1432729211],
        ["p1000/Proteomics/QEXACTIVEHF_1/tobiasko_20150526/20150526_30_MSCQ1_nodil_rep3.raw", 473966860, 1432857614],
        ["p1000/Proteomics/FUSION_2/roschi_20150527_Hela/20150527_17_fetuin.raw", 303573154, 1432890673],
        ["p1685/Proteomics/QEXACTIVE_2/cfortes_20150526_OID_1650_LFQ/20150529_11_OID_1650_AcPrec1.raw", 820211275, 1432716617],
        ["p1685/Proteomics/VELOS_1/cfortes_20150522_OID_1650_LFQ/20150522_10_OID1650_fetuin400amol.raw", 208637870, 1432371011],
        ["p987/Proteomics/FUSION_2/ruhrig_20150513_Large_FASP_Tissues/20150513_06_fetuin_1.raw", 451830098, 1431601814],
        ["p1352/Proteomics/QEXACTIVEHF_1/verabilan_20150529_PRM_SCX_chN/20150529_03_fetuin.raw", 192154238, 1432933251],
        ["p1118/Proteomics/TRIPLETOF_1/gtang_20150520/20150520_9_SWATH_klk5tc_18hctrl_2.wiff", 10379264, 1432208409],
        ["p1118/Proteomics/TRIPLETOF_1/tobiasko_20150406/20150406_5_PCT_liver_pool_4to6.wiff", 2805760, 1433446209],
        ["p1147/Proteomics/VELOS_1/chiawei_20150529/20150529_11_LCW_clean.raw", 191528596, 1432947012],
        ["p1132/Proteomics/FUSION_1/cfortes_20150604_Bovine_Set3_Chloe/20150604_08_Bov_1_13.raw", 1208290288, 1433470821],
        ["p1377/Proteomics/FUSION_1/gfasce_20150603_DeltaP600_lpqh/20150603_07_fetuin.raw", 356174600, 1433377813],
        ["p1431/Proteomics/TRIPLETOF_1/selevsek_20150601/20150601_010_nodil_1.wiff", 6696960, 1433251809],
        ["p1401/Proteomics/VELOS_1/ihmor_20150603_BigTwo_LabelEff/20150603_BigTwo_LabelEff06_Lys81T89.raw", 494918766, 1433357414],
        ["p1557/Proteomics/QEXACTIVE_2/schori_20150603_EM3736_BPCre_Vhl_R91W_NRL/20150603_11_EM3736_15v_1to5.raw", 943379749, 1433433019],
        ["p1579/Proteomics/QTRAP_1/poljakk_20150604/20150604_002_fetuin.wiff", 327680, 1433440810],
        ["p1797/Proteomics/QEXACTIVE_2/fsabino_20150429_patients_A07_A04_07/20150429_08a_fetuin.raw", 319248768, 1431017413],
        ["p1813/Proteomics/FUSION_2/ccantu_20150603_Bcl9HD1/20150603_03_WT_Colon_aBcl9.raw", 567789376, 1433373015],
        ["p1876/Proteomics/QEXACTIVEHF_1/paulboersema_20150430/20150602_16b_fetuin.raw", 245134201, 1433358012],
        ["p1876/Proteomics/QEXACTIVEHF_1/paulboersema_20150601/20150601_13_330_DIA_2h.raw", 2333941099, 1433250033],
        ["p1876/Proteomics/QEXACTIVEHF_1/paulboersema_20150601/20150605_37_fetuin_10fmol.raw", 214631721, 1433505611],
        ["p1839/Proteomics/QEXACTIVE_2/cfortes_20150520_OID_1512_LFQ/20150520_41_fetuin400amol_II.raw", 9045547, 1432392609],
        ["p1839/Proteomics/QEXACTIVE_2/cfortes_20150520_OID_1512_LFQ/20150520_59_CVE049.raw", 844720292, 1432518621],
        ["p1839/Proteomics/QEXACTIVE_2/cfortes_20150520_OID_1512_LFQ/20150520_79_fetuin400amol.raw", 220791614, 1432630212],
        ["p1740/Proteomics/TRIPLETOF_1/tiannan_20150527_plasma8/20150527_fetuin.wiff", 3346432, 1432949409],
        ["p1873/Proteomics/VELOS_1/cfortes_20150602_OID_1683_LFQ/20150602_08_RH_tube_31.raw", 651453146, 1433310616],
        ["p1809/Metabolomics/TSQ_2/dipalmas_20150602_carotenoids_tests/20150602_carotenoids_blank3.raw", 1804300, 1433512814],
        ["p1809/Metabolomics/TSQ_2/dipalmas_20150602_carotenoids_tests/20150602_carotenoids_Gd1a_gradient15min_02.raw", 752116, 1433512813]]
        return res

    def createFileOfGivenSize(self, folder, file, file_size):
        file = "{0}/{1}".format(folder, file)
        file = os.path.normpath(file)
        dir_name = os.path.dirname(file)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        f = open(file, "wb")
        f.seek(file_size/100 - 1)
        f.write("\0")
        f.close()
        print(os.stat(file).st_size)

    def setUp(self):
        files = self.fileList()
        for file in files:
            time.sleep(1)
            self.createFileOfGivenSize(self.folder, file[0], file[1])

    def tearDown(self):
        files = self.fileList()
        for file in files:
            file_name = "{0}/{1}".format(self.folder, file[0])
            os.remove(file_name)

