import argparse
import sys
import time
from datetime import datetime

import cnn.model_single as model_single
from cnn.constants import *
from cnn.data import *
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle

from cnn import model_branch
from utils import logger, angular_error_scalar

FLAGS = None


def training(images, labels):
    assert (len(images) == len(labels))
    run_name = datetime.now().strftime("%I:%M%p on %B %d, %Y")

    train_X, test_X, train_y, test_y = \
        train_test_split(images, labels, test_size=FLAGS.test_percent, random_state=0)
    train_X, train_y = split_to_patches(train_X, train_y)
    train_X, val_X, train_y, val_y = \
        train_test_split(train_X, train_y, test_size=FLAGS.valid_percent, random_state=0)

    learning_rate = FLAGS.learning_rate
    logger.info("learning rate: {0}".format(learning_rate))
    # Prepare for training
    num_batches_per_epoch = len(train_X) // FLAGS.batch_size

    with tf.Graph().as_default():

        # Define the input and label placeholders that will be used by
        # either single branch or multi branch model.
        image_placeholder = \
            tf.placeholder(tf.float32, (None, PATCH_SIZE[0], PATCH_SIZE[1],
                                        PATCH_SIZE[2]), name="Images")
        label_placeholder = tf.placeholder(tf.float32, (None, 2), name="Labels")

        # Single branch model
        if FLAGS.model == 'single':
            output = model_single.hyp_net_inference(image_placeholder)
            loss = model_single.hyp_net_loss(output, label_placeholder)
            train_op = model_single.hyp_net_training(loss, learning_rate)
            output_patch = model_single.hyp_net_inference(image_placeholder)
            init = tf.global_variables_initializer()
            saver = tf.train.Saver()

            # Summaries
            tf.summary.scalar("Loss", loss)

            with tf.Session() as sess:
                sess.run(init)
                summary_writer = tf.summary.FileWriter(os.path.join(log_dir, run_name), sess.graph)
                merged = tf.summary.merge_all()

                logger.info('Training...')
                non_improve_count = 0
                min_error = sys.maxsize
                for i in range(FLAGS.epochs):
                    train_X, train_y = shuffle(train_X, train_y)
                    for j in range(num_batches_per_epoch):
                        offset = j * FLAGS.batch_size
                        batch_X = train_X[offset:offset + FLAGS.batch_size]
                        batch_y = train_y[offset:offset + FLAGS.batch_size]
                        _, loss_value = sess.run([train_op, loss], feed_dict={image_placeholder: batch_X, label_placeholder: batch_y})
                        # loss_value = loss_value.item()
                        # logger.info("Training loss: %f" % loss_value)

                    loss_value, summary = sess.run([loss, merged], feed_dict={image_placeholder: val_X, label_placeholder: val_y})
                    loss_value = loss_value.item()  # convert to float
                    logger.info("Epoch: %d, Validation loss: %f"
                                % (i + 1, loss_value))
                    summary_writer.add_summary(summary, i)

                    # Early stop: If validation loss doesn't decrease for more
                    # than "--early_stop_threshold", then stop the training
                    if loss_value < min_error:
                        min_error = loss_value
                    else:
                        non_improve_count += 1
                    if non_improve_count > FLAGS.early_stop_threshold:
                        break

                saver.save(sess, check_ptr_dir)

                angular_errors = []
                for i in range(len(test_X)):
                    patches, labels = split_to_patches(np.asarray([test_X[i]]), np.asarray([test_y[i]]))
                    local_estimation = sess.run(output_patch, feed_dict={image_placeholder: patches, label_placeholder: labels})
                    angular_loss = angular_error_scalar(local_estimation, labels)
                    angular_errors.append(angular_loss)
                mean_error = np.mean(angular_errors)
                median_error = np.median(angular_errors)
                logger.info("########## Comparison by angular error: Mean is %s, Median is %s" % (mean_error, median_error))
                summary_writer.close()

        elif FLAGS.model == 'multiple':
            ground_truth_score = tf.placeholder(tf.float32, (None, 2), name="Ground_Truth_Score")

            outputA, outputB = model_branch.hyp_net_inference(image_placeholder)
            hyp_loss = model_branch.hyp_net_loss(outputA, outputB, label_placeholder)
            hyp_train_op = model_branch.hyp_net_training(hyp_loss, learning_rate)
            hyp_eval_correct = model_branch.hyp_net_evaluation(outputA, outputB, label_placeholder)
            calc_gt_score = model_branch.calc_ground_truth_score(outputA, outputB, label_placeholder)

            output_sel = model_branch.sel_net_inference(image_placeholder)
            sel_loss = model_branch.sel_net_loss(output_sel, ground_truth_score)
            sel_train_op = model_branch.sel_net_training(sel_loss, learning_rate)
            sel_eval_correct = model_branch.sel_net_loss(output_sel, ground_truth_score)
            output_patch = model_branch.inference(outputA, outputB, output_sel)
            init = tf.global_variables_initializer()
            saver = tf.train.Saver()

            # Summaries
            tf.summary.scalar("Hyp_Training_Loss", hyp_loss)
            tf.summary.scalar("Sel_Training_Loss", sel_loss)

            with tf.Session() as sess:
                sess.run(init)
                summary_writer = tf.summary.FileWriter(os.path.join(log_dir, run_name), sess.graph)
                merged = tf.summary.merge_all()

                logger.info('Training HypNet...')
                non_improve_count = 0
                min_error = sys.maxsize
                hyp_train_epoch = 0
                for i in range(FLAGS.epochs):
                    train_X, train_y = shuffle(train_X, train_y)
                    for j in range(num_batches_per_epoch):
                        offset = j * FLAGS.batch_size
                        batch_X = train_X[offset:offset + FLAGS.batch_size]
                        batch_y = train_y[offset:offset + FLAGS.batch_size]
                        _, summary = sess.run([hyp_train_op, merged],
                                              feed_dict={image_placeholder: batch_X, label_placeholder: batch_y, ground_truth_score: batch_y})
                    loss_value = sess.run(hyp_eval_correct, feed_dict={image_placeholder: val_X, label_placeholder: val_y})
                    loss_value = loss_value.item()  # convert to float
                    logger.info("Epoch: %d, Hyp Validation loss: %f" % (i + 1, loss_value))

                    if loss_value < min_error:
                        min_error = loss_value
                    else:
                        non_improve_count += 1
                    if non_improve_count > FLAGS.early_stop_threshold:
                        break

                    hyp_train_epoch += 1
                    summary_writer.add_summary(summary, hyp_train_epoch)
                a, b = sess.run([outputA, outputB], feed_dict={image_placeholder: val_X, label_placeholder: val_y})
                logger.info("%s \n%s" % (a, b))

                logger.info("Finish training HypNet. Test set loss: %s" % loss_value)

                logger.info('Training SelNet...')
                non_improve_count = 0
                min_error = sys.maxsize
                gt_score_train = sess.run(calc_gt_score, feed_dict={image_placeholder: train_X, label_placeholder: train_y})
                gt_score_val = sess.run(calc_gt_score, feed_dict={image_placeholder: val_X, label_placeholder: val_y})
                for i in range(FLAGS.epochs):
                    train_X, gt_score_train = shuffle(train_X, gt_score_train)
                    for j in range(num_batches_per_epoch):
                        offset = j * FLAGS.batch_size
                        start_time = time.time()
                        batch_X, batch_gt_score = train_X[offset:offset + FLAGS.batch_size], \
                                                  gt_score_train[offset:offset + FLAGS.batch_size]
                        _, summary = sess.run([sel_train_op, merged],
                                              feed_dict={image_placeholder: batch_X, label_placeholder: batch_gt_score, ground_truth_score: batch_gt_score})
                        duration = time.time() - start_time
                    loss_value = sess.run(sel_eval_correct,
                                          feed_dict={image_placeholder: val_X, label_placeholder: gt_score_val, ground_truth_score: gt_score_val})
                    loss_value = loss_value.item()  # convert to float
                    logger.info("Epoch: %d, Sel Validation loss: %f" % (i + 1, loss_value))

                    if loss_value < min_error:
                        min_error = loss_value
                    else:
                        non_improve_count += 1
                    if non_improve_count > FLAGS.early_stop_threshold:
                        break

                    summary_writer.add_summary(summary, i + hyp_train_epoch)
                saver.save(sess, check_ptr_dir)

                angular_errors = []
                for i in range(len(test_X)):
                    patches, labels = split_to_patches(np.asarray([test_X[i]]), np.asarray([test_y[i]]))
                    local_estimation = sess.run(output_patch, feed_dict={image_placeholder: patches, label_placeholder: labels})
                    angular_loss = angular_error_scalar(local_estimation, labels)
                    angular_errors.append(angular_loss)
                mean_error = np.mean(angular_errors)
                median_error = np.median(angular_errors)
                logger.info("########## Comparison by angular error: Mean is %s, Median is %s" % (mean_error, median_error))
                summary_writer.close()


def main(_):
    data_set_name = 'Canon5D'
    images, labels = load_data(data_set_name, debug=FLAGS.debug)
    training(images, labels)


if __name__ == "__main__":
    # Sequence of training between the two networks?
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Debug mode.')

    parser.add_argument(
        '--learning_rate',
        type=float,
        default=0.01,
        help='Initial learning rate.'
    )

    parser.add_argument(
        '--epochs',
        type=int,
        default=10,
        help='Number of steps to run trainer.'
    )

    parser.add_argument(
        '--batch_size',
        type=int,
        default=64,
        help='Number of data item in a batch.'
    )

    parser.add_argument(
        '--early_stop_threshold',
        type=int,
        default=5,
        help='Number of epoch without improvement to early stop'
    )

    parser.add_argument(
        '--test_percent',
        type=int,
        default=0.2,
        help='Number of steps to run trainer.'
    )

    parser.add_argument(
        '--valid_percent',
        type=int,
        default=0.2,
        help='Number of steps to run trainer.'
    )

    parser.add_argument(
        '--model',
        choices=['single', 'multiple'],
        default='multiple',
        help='Model of the network')

    FLAGS, unparsed = parser.parse_known_args()
    tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
