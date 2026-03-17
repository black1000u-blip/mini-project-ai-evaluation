"""Submission model — stores student submissions and evaluation results."""

from datetime import datetime, timezone

from bson import ObjectId


class SubmissionModel:
    def __init__(self, db):
        self.collection = db['submissions']

    def create(self, student_id, assignment_id, file_path, file_type):
        submission = {
            'student_id': student_id,
            'assignment_id': assignment_id,
            'file_path': file_path,
            'file_type': file_type,
            'extracted_text': '',
            'question_results': [],  # [{question_index, extracted_answer, similarity_score, marks_obtained, ai_marks}]
            'similarity_score': 0.0,
            'marks_obtained': 0.0,
            'feedback': {},
            'status': 'pending',  # pending | processing | evaluated | error
            'progress': 0,        # 0-100 percentage
            'progress_step': '',   # human-readable current step
            'error_message': '',
            'submitted_at': datetime.now(timezone.utc),
            'evaluated_at': None,
            'manual_check': False,
            'teacher_comments': '',
        }
        result = self.collection.insert_one(submission)
        submission['_id'] = result.inserted_id
        return self._serialize(submission)

    def update_evaluation(self, submission_id, extracted_text, question_results, 
                          similarity_score, marks_obtained, feedback):
        """Store evaluation results after AI processing."""
        self.collection.update_one(
            {'_id': ObjectId(submission_id)},
            {'$set': {
                'extracted_text': extracted_text,
                'question_results': question_results,
                'similarity_score': similarity_score,
                'marks_obtained': marks_obtained,
                'feedback': feedback,
                'status': 'evaluated',
                'progress': 100,
                'progress_step': 'Evaluation complete',
                'error_message': '',
                'evaluated_at': datetime.now(timezone.utc),
            }}
        )

    def update_manual_marks(self, submission_id, question_results, total_marks, teacher_comments=""):
        """Update marks manually by teacher."""
        self.collection.update_one(
            {'_id': ObjectId(submission_id)},
            {'$set': {
                'question_results': question_results,
                'marks_obtained': total_marks,
                'teacher_comments': teacher_comments,
                'manual_check': True,
                'status': 'evaluated'
            }}
        )

    def set_status(self, submission_id, status, error_message=None):
        updates = {'status': status}
        if error_message is not None:
            updates['error_message'] = error_message
        self.collection.update_one(
            {'_id': ObjectId(submission_id)},
            {'$set': updates}
        )

    def set_progress(self, submission_id, progress, step=''):
        """Update progress percentage (0-100) and step description."""
        self.collection.update_one(
            {'_id': ObjectId(submission_id)},
            {'$set': {'progress': progress, 'progress_step': step}}
        )

    def get_by_id(self, submission_id):
        doc = self.collection.find_one({'_id': ObjectId(submission_id)})
        return self._serialize(doc) if doc else None

    def get_by_student(self, student_id):
        docs = self.collection.find({'student_id': student_id}).sort('submitted_at', -1)
        return [self._serialize(d) for d in docs]

    def get_by_assignment(self, assignment_id):
        docs = self.collection.find({'assignment_id': assignment_id}).sort('submitted_at', -1)
        return [self._serialize(d) for d in docs]

    def get_all(self, status=None):
        query = {}
        if status:
            query['status'] = status
        docs = self.collection.find(query).sort('submitted_at', -1)
        return [self._serialize(d) for d in docs]

    def delete(self, submission_id):
        result = self.collection.delete_one({'_id': ObjectId(submission_id)})
        return result.deleted_count > 0

    def delete_by_assignment(self, assignment_id):
        """Delete all submissions for a given assignment."""
        result = self.collection.delete_many({'assignment_id': assignment_id})
        return result.deleted_count

    def count(self, status=None):
        query = {}
        if status:
            query['status'] = status
        return self.collection.count_documents(query)

    def average_score(self, assignment_id=None):
        """Get average similarity score for evaluated submissions."""
        match = {'status': 'evaluated'}
        if assignment_id:
            match['assignment_id'] = assignment_id
        pipeline = [
            {'$match': match},
            {'$group': {'_id': None, 'avg_score': {'$avg': '$similarity_score'}}}
        ]
        result = list(self.collection.aggregate(pipeline))
        return result[0]['avg_score'] if result else 0.0

    @staticmethod
    def _serialize(doc):
        if not doc:
            return None
        return {
            'id': str(doc['_id']),
            'student_id': doc['student_id'],
            'assignment_id': doc['assignment_id'],
            'file_path': doc.get('file_path', ''),
            'file_type': doc.get('file_type', ''),
            'extracted_text': doc.get('extracted_text', ''),
            'question_results': doc.get('question_results', []),
            'similarity_score': doc.get('similarity_score', 0.0),
            'marks_obtained': doc.get('marks_obtained', 0.0),
            'feedback': doc.get('feedback', {}),
            'status': doc.get('status', 'pending'),
            'progress': doc.get('progress', 0),
            'progress_step': doc.get('progress_step', ''),
            'error_message': doc.get('error_message', ''),
            'submitted_at': doc['submitted_at'].isoformat() if doc.get('submitted_at') else '',
            'evaluated_at': doc['evaluated_at'].isoformat() if doc.get('evaluated_at') else None,
            'manual_check': doc.get('manual_check', False),
            'teacher_comments': doc.get('teacher_comments', ''),
        }
