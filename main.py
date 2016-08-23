
import os.path
import time

import numpy as np
import tensorflow as tf
import cv2

import bouncing_balls as b
import layer_def as ld
import BasicConvLSTMCell

FLAGS = tf.app.flags.FLAGS

tf.app.flags.DEFINE_string('train_dir', '../checkpoints/train_store',
                            """dir to store trained net""")
tf.app.flags.DEFINE_integer('hidden_size', 20,
                            """size of hidden layer""")
tf.app.flags.DEFINE_integer('seq_length', 20,
                            """size of hidden layer""")
tf.app.flags.DEFINE_integer('max_step', 200000,
                            """max num of steps""")
tf.app.flags.DEFINE_float('keep_prob', .8,
                            """for dropout""")
tf.app.flags.DEFINE_float('lr', .001,
                            """for dropout""")
tf.app.flags.DEFINE_integer('batch_size', 64,
                            """batch size for training""")
tf.app.flags.DEFINE_float('weight_init', .1,
                            """weight init for fully connected layers""")

fourcc = cv2.cv.CV_FOURCC('m', 'p', '4', 'v') 

def generate_bouncing_ball_sample(batch_size, seq_length, shape, num_balls):
  dat = np.zeros((batch_size, seq_length, shape, shape, 3))
  for i in xrange(batch_size):
    dat[i, :, :, :, :] = b.bounce_vec(32, num_balls, seq_length)
  return dat 

def train():
  """Train ring_net for a number of steps."""
  with tf.Graph().as_default():
    # make inputs
    x = tf.placeholder(tf.float32, [None, FLAGS.seq_length, 32, 32, 3])

    # possible dropout inside
    keep_prob = tf.placeholder("float")
    x_dropout = tf.nn.dropout(x, keep_prob)

    # create network
    x_unwrap = []
    with tf.variable_scope('conv_lstm', initializer = tf.random_uniform_initializer(-.01, 0.1)):
      cell = BasicConvLSTMCell.BasicConvLSTMCell([8,8], [3,3], 64)
      state = tf.zeros([FLAGS.batch_size, 8, 8, 128])

    # conv peice in
    # conv1
    for i in xrange(FLAGS.seq_length):
      conv1 = ld.conv_layer(x_dropout[:,i,:,:,:], 3, 1, 32, "encode_1")
      # conv2
      conv2 = ld.conv_layer(conv1, 3, 2, 64, "encode_2")
      # conv3
      conv3 = ld.conv_layer(conv2, 3, 1, 64, "encode_3")
      # conv4
      conv4 = ld.conv_layer(conv3, 3, 2, 128, "encode_4")
      # conv5
      conv5 = ld.conv_layer(conv4, 1, 1, 64, "encode_5")
  
      # conv lstm cell 
      y_1, new_state = cell(conv5, state)
  
      # transpose conv out
      # conv10
      conv10 = ld.transpose_conv_layer(y_1, 1, 1, 128, "decode_10")
      # conv11
      conv11 = ld.transpose_conv_layer(conv10, 3, 2, 64, "decode_11")
      # conv12
      conv12 = ld.transpose_conv_layer(conv11, 3, 1, 64, "decode_12")
      # conv13
      conv13 = ld.transpose_conv_layer(conv12, 3, 2, 32, "decode_13")
      # conv14
      x_1 = ld.transpose_conv_layer(conv13, 3, 1, 3, "decode_14", True) # set activation to linear
      x_unwrap.append(x_1)
   
      # set reuse to true after first go
      if i == 0:
        tf.get_variable_scope().reuse_variables()
  
    x_unwrap = tf.pack(x_unwrap)
    x_unwrap = tf.transpose(x_unwrap, [1,0,2,3,4])
    
    # calc total loss (compare x_t to x_t+1)
    loss = tf.nn.l2_loss(x[:,1:,:,:,:] - x_unwrap[:,:FLAGS.seq_length-1,:,:,:])
    tf.scalar_summary('loss', loss)

    # training
    train_op = tf.train.AdamOptimizer(FLAGS.lr).minimize(loss)
    
    # List of all Variables
    variables = tf.all_variables()

    # Build a saver
    saver = tf.train.Saver(tf.all_variables())   

    # Summary op
    summary_op = tf.merge_all_summaries()
 
    # Build an initialization operation to run below.
    init = tf.initialize_all_variables()

    # Start running operations on the Graph.
    sess = tf.Session()

    # init if this is the very time training
    print("init network from scratch")
    sess.run(init)

    # Summary op
    graph_def = sess.graph.as_graph_def(add_shapes=True)
    summary_writer = tf.train.SummaryWriter(FLAGS.train_dir, graph_def=graph_def)

    for step in xrange(FLAGS.max_step):
      dat = generate_bouncing_ball_sample(FLAGS.batch_size, FLAGS.seq_length, 32, FLAGS.num_balls)
      t = time.time()
      _, loss_r = sess.run([train_op, loss],feed_dict={x:dat, keep_prob:FLAGS.keep_prob})
      elapsed = time.time() - t
      print(loss_r)

      if step%100 == 0 and step != 0:
        summary_str = sess.run(summary_op, feed_dict={x:dat, keep_prob:FLAGS.keep_prob})
        summary_writer.add_summary(summary_str, step) 
        print("time per batch is " + str(elapsed))
      
      assert not np.isnan(loss_r), 'Model diverged with loss = NaN'

      if step%1000 == 0:
        checkpoint_path = os.path.join(FLAGS.train_dir, 'model.ckpt')
        saver.save(sess, checkpoint_path, global_step=step)  
        print("saved to " + FLAGS.train_dir)

        # make video
        print("now generating video!")
        video = cv2.VideoWriter()
        success = video.open("generated_video.mov", fourcc, 4, (180, 180), True)
        dat_gif = dat[:,:,:,:,:]
        for i in xrange(50):
          dat_gif = sess.run([x_unwrap],feed_dict={x:dat_gif, keep_prob:FLAGS.keep_prob})
          dat_gif = dat_gif[0]
          x_1_r = np.uint8(np.maximum(dat_gif[0,0,:,:,:], 0) * 255)
          new_im = cv2.resize(x_1_r, (180,180))
          video.write(new_im)
        video.release()


def main(argv=None):  # pylint: disable=unused-argument
  if tf.gfile.Exists(FLAGS.train_dir):
    tf.gfile.DeleteRecursively(FLAGS.train_dir)
  tf.gfile.MakeDirs(FLAGS.train_dir)
  train()

if __name__ == '__main__':
  tf.app.run()


