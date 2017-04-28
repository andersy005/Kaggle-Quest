##########################################################################
# Credits go to Aarshay Jain: https://github.com/aarshayj
##########################################################################


##########################################################################
# IMPORT STANDARD MODULES
##########################################################################


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pydot
import os
from scipy.stats.mstats import chisquare, mode

from sklearn.linear_model import LogisticRegression
from sklearn.cross_validation import KFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.ensemble import AdaBoostClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier, export_graphviz
from sklearn.model_selection import GridSearchCV
from sklearn import metrics, cross_validation
from sklearn.feature_selection import RFE, RFECV
import io
import xgboost as xgb
from xgboost.sklearn import XGBClassifier


##########################################################################
# GENERIC MODEL CLASS
##########################################################################


class GenericModelClass(object):
    """
    This class contains the generic classiciation functions and variable
    definitions applicable across all models.
    """

    def __init__(self, model, data_train, data_test, target,
                 predictors=[], cv_folds=5, scoring_metric='accuracy'):
        """Initialization"""
        self.model = model            # an instance of particular model class
        self.data_train = data_train   # training data
        self.data_test = data_test     # testing data
        self.target = target
        self.cv_folds = cv_folds
        self.predictors = predictors
        self.train_predictions = []
        self.train_pred_prob = []
        self.test_predictions = []
        self.test_pred_prob = []
        self.num_target_class = len(data_train[target].unique())

        # define scoring metric:
        self.scoring_metric = scoring_metric

        # grid-search objects:
        self.gridsearch_class = None
        self.gridsearch_result = None

        # Define a Series object to store generic classidication model
        # outcomes:
        self.classification_output = pd.Series(index=['ModelID', 'Accuracy', 'CVScore_mean',
                                                      'CVScore_std', 'AUC', 'ActualScore(manual entry)',
                                                      'CVMethod', 'ConfusionMatrix', 'Predictors'])

        # not to be used for all but most
        self.feature_imp = None

    def set_predictors(self, predictors):
        """
        Modify and get predictors for the model.
        """
        self.predictors = predictors

    def get_predictors(self):
        return self.predictors

    def get_test_predictions(self, getprob=False):
        if getprob:
            return self.test_pred_prob

        else:
            return self.test_predictions

    def get_feature_importance(self):
        return self.feature_imp

    def set_scoring_metric(scoring_metric):
        self.scoring_metric = scoring_metric

    def KFold_CrossValidation(self, scoring_metric):
        """
        Implement K-Fold cross-validation.
        Generate cross validation folds for the training dataset.
        """

        error = cross_validation.cross_val_score(self.model,
                                                 self.data_train[
                                                     self.predictors],
                                                 self.data_train[self.target],
                                                 cv=self.cv_folds,
                                                 scoring=scoring_metric, n_jobs=4)

        return {'mean_error': np.mean(error),
                'std_error': np.std(error),
                'all_error': error}

    def RecursiveFeatureElimination(self, nfeat=None, step=1, inplace=False):
        """
          # Implement recursive feature elimination
          # Inputs:
          #     nfeat - the num of top features to select
          #     step - the number of features to remove at each step
          #     inplace - True: modiy the data of the class with the data after RFE
          # Returns:
          #     selected - a series object containing the selected features
         """
        rfe = RFE(self.model, n_features_to_select=nfeat, step=step)
        rfe.fit(self.data_train[self.predictors], self.data_train[self.target])
        ranks = pd.Series(rfe.ranking_, index=self.predictors)
        selected = ranks.loc[rfe.support_]

        if inplace:
            self.set_predictors(selected.index.tolist())

        return selected

    def RecursiveFeatureEliminationCV(self, step=1, inplace=False):
        """
        Performs similar function as RFE but with CV.
        It removes features similar to RFE but the the importance of the
        group of features is based on the cross-validation score. The set 
        of features with highest cross validation scores is then chosen. 
        The difference from RFE is that the #features is not an input but 
        selected by model.

        """

        rfecv = RFECV(self.model, step=step, cv=self.cv_folds,
                      scoring=self.scoring_metric)

        rfecv.fit(self.data_train[self.predictors],
                  self.data_train[self.target])

        # n - step*(number of iter - 1)
        min_nfeat = len(self.predictors) - step * (len(rfecv.grid_scores_) - 1)

        plt.xlabel("Number of features selected")
        plt.ylabel("Cross validation score (nb of correct classification)")
        plt.plot(range(min_nfeat, len(self.predictors) + 1, step),
                 rfecv.grid_scores_)
        plt.show(block=False)

        ranks = pd.Series(rfecv.ranking_, index=self.predictors)
        selected = ranks.loc[rfec.support_]

        if inplace:
            self.set_predictors(selected.index.tolist())

        return ranks

    def GridSearch(self, param_grid, n_jobs=1, iid=True, cv=None):
        """
        Perform Grid-Search with cv
        """

        self.gridsearch_class = GridSearchCV(self.model, param_grid=param_grid,
                                             scoring=self.scoring_metric,
                                             n_jobs=n_jobs,
                                             iid=iid,
                                             cv=cv)
        self.gridsearch_class.fit(
            self.data_train[self.predictors], self.data_train[self.target])

        print('Grid Search Results: \n')

        self.gridsearch_result = pd.DataFrame()

        for key in param_grid.keys():
            self.gridsearch_result[key] = [x[0][key]
                                           for x in self.gridsearch_class.grid_scores_]

        self.gridsearch_result['meanCV'] = [x[1]
                                            for x in self.gridsearch_class.grid_scores_]

        self.gridsearch_result['stdCV'] = [
            np.std(x[2]) for x in self.gridsearch_class.grid_scores_]

        print(self.gridsearch_result)

        print('\nBest Parameters: ', self.gridsearch_class.best_params_)
        print('\nBest Score: ', self.gridsearch_class.best_score_)

    def calc_model_characteristics(self, performCV=True):
        """
        Determine key metrics to analyze the classification model. These are stored in the 
        classification_output series object belong to this class.
        """

        self.classification_output['Accuracy'] = metrics.accuracy_score(
            self.data_train[self.target],
            self.train_predictions)

        # define scoring metric:
        if self.scoring_metric == 'roc_auc':
            self.classification_output['ScoringMetric'] = metrics.roc_auc_score(
                self.data_train[self.target],
                self.train_pred_prob[:, 1])
        elif self.scoring_metric == 'log_loss':
            self.classification_output['ScoringMetric'] = metrics.log_loss(
                self.data_train[self.target],
                self.train_pred_prob)

        if performCV:
            cv_score = self.KFold_CrossValidation(
                scoring_metric=self.scoring_metric)

        else:
            cv_score = {'mean_error': 0.0, 'std_error': 0.0}

        self.classification_output[
            'CVMethod'] = 'KFold - ' + str(self.cv_folds)
        self.classification_output['CVScore_mean'] = cv_score['mean_error']
        self.classification_output['CVScore_std'] = cv_score['std_error']

        if self.num_target_class < 3:
            self.classification_output['AUC'] = metrics.roc_auc_score(self.data_train[self.target],
                                                                      self.train_pred_prob[:, 1])
        else:
            self.classification_output['AUC'] = np.nan

        self.classification_output['ConfusionMatrix'] = pd.crosstab(self.data_train[self.target],
                                                                    self.train_predictions).to_string()
        self.classification_output['Predictors'] = str(self.predictors)

    def printReport(self):
        """
        Print the metrics determined in the calc_model_characteristics()
        function.
        """
        print('\n*************Model Report*************')
        print('\n*                                    *')
        print('\n*                                    *')
        print('\n**************************************')

        print('\nConfusion Matrix:')
        print(pd.crosstab(self.data_train[
              self.target], self.train_predictions))
        print('\nNote: rows - actual; col- predicted')
        print("\nTrain (Accuracy) : %s" % "{0:.5%}".format(
            self.classification_output['Accuracy']))

        if self.scoring_metric != 'accuracy':
            print("Train (%s) : %f" % (self.scoring_metric,
                                       self.classification_output['ScoringMetric']))

        print("AUC : %s" % "{0:.5%}".format(self.classification_output['AUC']))

        print("CV score (Specified Metric) : Mean - {:f}| Std - {:f}".format(
            self.classification_output['CVScore_mean'],
            self.classification_output['CVScore_std']))
