"""Teacher routes — create assignments, view submissions, analytics."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

teacher_bp = Blueprint('teacher', __name__)


def _get_db():
    from app import db
    return db


def _require_teacher():
    claims = get_jwt()
    if claims.get('role') != 'teacher':
        return None, (jsonify({'error': 'Teacher access only'}), 403)
    return get_jwt_identity(), None


@teacher_bp.route('/assignment', methods=['POST'])
@jwt_required()
def create_assignment():
    user_id, err = _require_teacher()
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    title = data.get('title', '').strip()
    subject = data.get('subject', '').strip()
    full_model_text = data.get('model_answer', '').strip() # Single block of text
    default_total = data.get('total_marks', 100)

    if not title or not subject or not full_model_text:
        return jsonify({'error': 'Title, subject, and model_answer are required'}), 400

    from services.nlp_preprocessing import parse_model_answers
    questions = parse_model_answers(full_model_text, default_total)

    if not questions:
        return jsonify({'error': 'No questions found in text'}), 400

    # Calculate final total marks from parsed questions
    total_marks = sum(q['marks'] for q in questions)

    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    assignment = model.create(user_id, title, subject, questions, total_marks)

    return jsonify({
        'message': f'Assignment created with {len(questions)} questions.',
        'assignment': assignment,
    }), 201


@teacher_bp.route('/edit-marks/<submission_id>', methods=['POST'])
@jwt_required()
def edit_marks(submission_id):
    user_id, err = _require_teacher()
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    question_results = data.get('question_results', [])
    teacher_comments = data.get('teacher_comments', '').strip()

    if not isinstance(question_results, list):
        return jsonify({'error': 'question_results must be a list'}), 400

    from models.submission import SubmissionModel
    from models.assignment import AssignmentModel
    
    db = _get_db()
    submission_model = SubmissionModel(db)
    assignment_model = AssignmentModel(db)

    submission = submission_model.get_by_id(submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404

    # Verify teacher owns this assignment
    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment or assignment['teacher_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    total_marks = 0
    for res in question_results:
        try:
            # Safely handle None or invalid values for marks
            marks_val = res.get('marks_obtained')
            if marks_val is not None:
                total_marks += float(marks_val)
        except (ValueError, TypeError):
            pass # Ignore if conversion to float fails

    submission_model.update_manual_marks(submission_id, question_results, total_marks, teacher_comments)

    return jsonify({
        'message': 'Marks updated successfully',
        'marks_obtained': total_marks
    }), 200


@teacher_bp.route('/assignments', methods=['GET'])
@jwt_required()
def list_assignments():
    user_id, err = _require_teacher()
    if err:
        return err

    from models.assignment import AssignmentModel
    model = AssignmentModel(_get_db())
    assignments = model.get_all(teacher_id=user_id, active_only=False)

    return jsonify({'assignments': assignments}), 200


@teacher_bp.route('/submissions', methods=['GET'])
@jwt_required()
def view_submissions():
    user_id, err = _require_teacher()
    if err:
        return err

    assignment_id = request.args.get('assignment_id')

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    from models.user import UserModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)
    user_model = UserModel(db)

    if assignment_id:
        # Verify this assignment belongs to the teacher
        assignment = assignment_model.get_by_id(assignment_id)
        if not assignment or assignment['teacher_id'] != user_id:
            return jsonify({'error': 'Assignment not found'}), 404
        submissions = submission_model.get_by_assignment(assignment_id)
    else:
        # Get all submissions for this teacher's assignments
        teacher_assignments = assignment_model.get_all(teacher_id=user_id, active_only=False)
        assignment_ids = [a['id'] for a in teacher_assignments]
        submissions = []
        for aid in assignment_ids:
            submissions.extend(submission_model.get_by_assignment(aid))

    # Enrich with student name and assignment title
    for s in submissions:
        student = user_model.get_by_id(s['student_id'])
        s['student_name'] = student['name'] if student else 'Unknown'
        assignment = assignment_model.get_by_id(s['assignment_id'])
        s['assignment_title'] = assignment['title'] if assignment else 'Unknown'
        s['total_marks'] = assignment['total_marks'] if assignment else 0

    return jsonify({'submissions': submissions}), 200


@teacher_bp.route('/submission/<submission_id>', methods=['GET'])
@jwt_required()
def get_submission(submission_id):
    user_id, err = _require_teacher()
    if err:
        return err

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel
    from models.user import UserModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)
    user_model = UserModel(db)

    submission = submission_model.get_by_id(submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404

    assignment = assignment_model.get_by_id(submission['assignment_id'])
    if not assignment or assignment['teacher_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    student = user_model.get_by_id(submission['student_id'])
    submission['student_name'] = student['name'] if student else 'Unknown'
    submission['assignment_title'] = assignment['title']
    submission['total_marks'] = assignment['total_marks']

    return jsonify({'submission': submission, 'assignment': assignment}), 200


@teacher_bp.route('/reports', methods=['GET'])
@jwt_required()
def reports():
    user_id, err = _require_teacher()
    if err:
        return err

    from models.assignment import AssignmentModel
    from models.submission import SubmissionModel

    db = _get_db()
    assignment_model = AssignmentModel(db)
    submission_model = SubmissionModel(db)

    assignments = assignment_model.get_all(teacher_id=user_id, active_only=False)

    report_data = []
    for a in assignments:
        subs = submission_model.get_by_assignment(a['id'])
        evaluated = [s for s in subs if s['status'] == 'evaluated']

        avg_score = 0.0
        avg_marks = 0.0
        if evaluated:
            avg_score = sum(s['similarity_score'] for s in evaluated) / len(evaluated)
            avg_marks = sum(s['marks_obtained'] for s in evaluated) / len(evaluated)

        report_data.append({
            'assignment_id': a['id'],
            'title': a['title'],
            'subject': a['subject'],
            'total_marks': a['total_marks'],
            'total_submissions': len(subs),
            'evaluated_count': len(evaluated),
            'pending_count': len(subs) - len(evaluated),
            'average_similarity': round(avg_score * 100, 2),
            'average_marks': round(avg_marks, 2),
        })

    return jsonify({'reports': report_data}), 200
