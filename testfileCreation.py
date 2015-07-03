import unittest
import os
from fgcz_biobeamer import BioBeamer
from fgcz_biobeamer import Checker
import time
import tempfile

class TestFileFilter(unittest.TestCase):
    """
    run
        python -m unittest -v fgcz_biobeamer

    """
    folder = tempfile.gettempdir()
    folder = "{0}/{1}".format(folder, "testBiobeamer")
    out_folder = folder

    BIG_SIZE = 1000000
    MEDIUM_SIZE = 10000
    SMALL_SIZE = 1000

    SMALL_TIME = 900
    MEDIUM_TIME = 1800
    BIG_TIME = 3600

    def test_triple_tof(self):
        print("hello world")
        time.sleep(5)
        bio_beamer = BioBeamer(
            source_path=self.folder,
            target_path=self.out_folder
        )
        bio_beamer.set_para('min_time_diff', 1)
        bio_beamer.set_para('max_time_diff', 3700)
        bio_beamer.set_para('pattern', ".+\.raw")
        bio_beamer.set_para('simulate', True)
        bio_beamer.print_para()
        bio_beamer.run()
        assert bio_beamer.results == []

    #def test_beam_and_check(self):
    #    self.triple_tof()

    def checker(self):
        print("hello world")
        time.sleep(5)
        checker = Checker(
            source_path=self.folder,
            target_path=self.folder
        )
        checker.set_para('min_time_diff', 10)
        checker.set_para('pattern', ".+\.raw")
        checker.print_para()
        checker.run()

    def fileList(self):
        res = [["p1000/Proteomics/FUSION_1/pgehrig_20150526_TiO2_NH3_Pyr/20150526_10_fetuin_40fmol.raw", self.BIG_SIZE, self.BIG_TIME],
        ["p1000/Proteomics/FUSION_1/pgehrig_20150602_30PP_CE/20150602_02_30PP_400fmol.raw", self.BIG_SIZE, self.MEDIUM_TIME],
        ["p1000/Proteomics/QEXACTIVEHF_1/tobiasko_20150526/20150526_12_400amol_fetuin_incl_iRT_1in800.raw", self.BIG_SIZE, self.SMALL_TIME],
        ["p1000/Proteomics/QEXACTIVEHF_1/tobiasko_20150526/20150526_30_MSCQ1_nodil_rep3.raw", self.BIG_SIZE, self.BIG_TIME],
        ["p1000/Proteomics/FUSION_2/roschi_20150527_Hela/20150527_17_fetuin.raw", self.BIG_SIZE, self.MEDIUM_TIME],
        ["p1685/Proteomics/QEXACTIVE_2/cfortes_20150526_OID_1650_LFQ/20150529_11_OID_1650_AcPrec1.raw", self.BIG_SIZE, self.SMALL_TIME],
        ["p1685/Proteomics/VELOS_1/cfortes_20150522_OID_1650_LFQ/20150522_10_OID1650_fetuin400amol.raw", self.BIG_SIZE, self.BIG_TIME],
        ["p987/Proteomics/FUSION_2/ruhrig_20150513_Large_FASP_Tissues/20150513_06_fetuin_1.raw", self.BIG_SIZE, self.MEDIUM_TIME],
        ["p1352/Proteomics/QEXACTIVEHF_1/verabilan_20150529_PRM_SCX_chN/20150529_03_fetuin.raw", self.BIG_SIZE, self.SMALL_TIME],
        ["p1118/Proteomics/TRIPLETOF_1/gtang_20150520/20150520_9_SWATH_klk5tc_18hctrl_2.wiff", self.BIG_SIZE, self.BIG_TIME],
        ["p1118/Proteomics/TRIPLETOF_1/tobiasko_20150406/20150406_5_PCT_liver_pool_4to6.wiff", self.BIG_SIZE, self.MEDIUM_TIME],
        ["p1147/Proteomics/VELOS_1/chiawei_20150529/20150529_11_LCW_clean.raw", self.MEDIUM_SIZE, self.SMALL_TIME],
        ["p1132/Proteomics/FUSION_1/cfortes_20150604_Bovine_Set3_Chloe/20150604_08_Bov_1_13.raw", self.MEDIUM_SIZE, self.BIG_TIME],
        ["p1377/Proteomics/FUSION_1/gfasce_20150603_DeltaP600_lpqh/20150603_07_fetuin.raw", self.MEDIUM_SIZE, self.MEDIUM_TIME],
        ["p1431/Proteomics/TRIPLETOF_1/selevsek_20150601/20150601_010_nodil_1.wiff", self.MEDIUM_SIZE, self.SMALL_TIME],
        ["p1401/Proteomics/VELOS_1/ihmor_20150603_BigTwo_LabelEff/20150603_BigTwo_LabelEff06_Lys81T89.raw", self.MEDIUM_SIZE, self.BIG_TIME],
        ["p1557/Proteomics/QEXACTIVE_2/schori_20150603_EM3736_BPCre_Vhl_R91W_NRL/20150603_11_EM3736_15v_1to5.raw", self.MEDIUM_SIZE, self.MEDIUM_TIME],
        ["p1579/Proteomics/QTRAP_1/poljakk_20150604/20150604_002_fetuin.wiff", self.MEDIUM_SIZE, self.MEDIUM_TIME],
        ["p1797/Proteomics/QEXACTIVE_2/fsabino_20150429_patients_A07_A04_07/20150429_08a_fetuin.raw", self.MEDIUM_SIZE, self.BIG_TIME],
        ["p1813/Proteomics/FUSION_2/ccantu_20150603_Bcl9HD1/20150603_03_WT_Colon_aBcl9.raw", self.MEDIUM_SIZE, self.MEDIUM_TIME],
        ["p1876/Proteomics/QEXACTIVEHF_1/paulboersema_20150430/20150602_16b_fetuin.raw", self.MEDIUM_SIZE, self.SMALL_TIME],
        ["p1876/Proteomics/QEXACTIVEHF_1/paulboersema_20150601/20150601_13_330_DIA_2h.raw", self.MEDIUM_SIZE, self.BIG_TIME],
        ["p1876/Proteomics/QEXACTIVEHF_1/paulboersema_20150601/20150605_37_fetuin_10fmol.raw", self.MEDIUM_SIZE, self.MEDIUM_TIME],
        ["p1839/Proteomics/QEXACTIVE_2/cfortes_20150520_OID_1512_LFQ/20150520_41_fetuin400amol_II.raw", self.SMALL_SIZE, self.SMALL_TIME],
        ["p1839/Proteomics/QEXACTIVE_2/cfortes_20150520_OID_1512_LFQ/20150520_59_CVE049.raw", self.SMALL_SIZE, self.BIG_TIME],
        ["p1839/Proteomics/QEXACTIVE_2/cfortes_20150520_OID_1512_LFQ/20150520_79_fetuin400amol.raw", self.SMALL_SIZE, self.MEDIUM_TIME],
        ["p1740/Proteomics/TRIPLETOF_1/tiannan_20150527_plasma8/20150527_fetuin.wiff", self.SMALL_SIZE, self.SMALL_TIME],
        ["p1873/Proteomics/VELOS_1/cfortes_20150602_OID_1683_LFQ/20150602_08_RH_tube_31.raw", self.SMALL_SIZE, self.BIG_TIME],
        ["p1809/Metabolomics/TSQ_2/dipalmas_20150602_carotenoids_tests/20150602_carotenoids_blank3.raw", self.SMALL_SIZE, self.MEDIUM_TIME],
        ["p1809/Metabolomics/TSQ_2/dipalmas_20150602_carotenoids_tests/20150602_carotenoids_Gd1a_gradient15min_02.raw", self.SMALL_SIZE, self.SMALL_TIME]]
        return res

    def createFileOfGivenSize(self, folder, file, file_size, modification_time ):
        file = "{0}/{1}".format(folder, file)
        file = os.path.normpath(file)
        dir_name = os.path.dirname(file)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        f = open(file, "wb")
        f.seek(file_size)
        f.write('\0')
        f.close()
        os.utime(file, (modification_time, modification_time))
        print(os.stat(file).st_size)

    def setUp(self):
        files = self.fileList()
        print("len files {0}".format(len(files)))
        current_time = time.time()

        for file in files:
            self.createFileOfGivenSize(self.folder, file[0], file[1], current_time - file[2])

    # def tearDown(self):
    #     files = self.fileList()
    #     for file in files:
    #         file_name = "{0}/{1}".format(self.folder)
    #         os.remove(file_name)